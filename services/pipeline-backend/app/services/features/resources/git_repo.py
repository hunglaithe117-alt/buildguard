"""
Git Repository Resource Manager.

Provides shared access to cloned git repositories for feature extraction.
"""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from git import Repo

from app.domain.entities import ImportedRepository
from app.services.commit_replay import ensure_commit_exists
from app.services.github.github_app import get_installation_token
from buildguard_common.utils.locking import repo_lock

from ..base import ExtractionContext

logger = logging.getLogger(__name__)

REPOS_DIR = Path("../repo-data/repos")
REPOS_DIR.mkdir(parents=True, exist_ok=True)


class GitRepoResource:
    """
    Manages access to a cloned git repository.
    
    Usage:
        resource = GitRepoResource.from_context(context)
        if resource.is_available:
            git_repo = resource.repo
            # Use git_repo...
    """
    
    CACHE_KEY = "git_repo_resource"
    
    def __init__(
        self,
        repo_path: Path,
        git_repo: Optional[Repo] = None,
        commit_sha: Optional[str] = None,
        effective_sha: Optional[str] = None,
    ):
        self.repo_path = repo_path
        self._git_repo = git_repo
        self.commit_sha = commit_sha
        self.effective_sha = effective_sha
    
    @property
    def repo(self) -> Optional[Repo]:
        """Get the GitPython Repo object."""
        if self._git_repo is None and self.repo_path.exists():
            self._git_repo = Repo(str(self.repo_path))
        return self._git_repo
    
    @property
    def is_available(self) -> bool:
        """Check if the repository is available."""
        return self.repo_path.exists() and self.effective_sha is not None
    
    @classmethod
    def from_context(
        cls,
        context: ExtractionContext,
        commit_sha: Optional[str] = None,
    ) -> "GitRepoResource":
        """
        Get or create a GitRepoResource from the extraction context.
        
        Uses caching to avoid redundant clone operations.
        """
        # Check cache first
        if context.has_cache(cls.CACHE_KEY):
            cached = context.get_cache(cls.CACHE_KEY)
            if isinstance(cached, GitRepoResource):
                return cached
        
        repo = context.repo
        if not repo:
            return cls(Path(""), None, None, None)
        
        repo_path = REPOS_DIR / str(repo.id)
        commit_sha = commit_sha or context.build_sample.tr_original_commit
        
        if not commit_sha:
            if context.workflow_run:
                commit_sha = context.workflow_run.head_sha
        
        if not commit_sha:
            return cls(repo_path, None, commit_sha, None)
        
        try:
            with repo_lock(str(repo.id)):
                cls._ensure_repo(repo, repo_path, context.db)
                cls._run_git(repo_path, ["fetch", "origin"])
                
                # Ensure commit exists
                token = cls._get_token(repo, context.db)
                effective_sha = ensure_commit_exists(
                    repo_path, commit_sha, repo.full_name, token
                )
            
            resource = cls(repo_path, None, commit_sha, effective_sha)
            context.set_cache(cls.CACHE_KEY, resource)
            return resource
            
        except Exception as e:
            logger.error(f"Failed to setup git repo: {e}")
            return cls(repo_path, None, commit_sha, None)
    
    @staticmethod
    def _ensure_repo(repo: ImportedRepository, repo_path: Path, db) -> None:
        """Ensure the repository is cloned."""
        if repo_path.exists():
            if (repo_path / ".git").exists():
                return
            else:
                shutil.rmtree(repo_path)
        
        auth_url = f"https://github.com/{repo.full_name}.git"
        token = GitRepoResource._get_token(repo, db)
        
        if token:
            if repo.installation_id:
                auth_url = f"https://x-access-token:{token}@github.com/{repo.full_name}.git"
            else:
                auth_url = f"https://{token}@github.com/{repo.full_name}.git"
        
        logger.info(f"Cloning {repo.full_name} to {repo_path}")
        subprocess.run(
            ["git", "clone", auth_url, str(repo_path)],
            check=True,
            capture_output=True,
        )
    
    @staticmethod
    def _get_token(repo: ImportedRepository, db) -> Optional[str]:
        """Get GitHub token for authentication."""
        if repo.installation_id:
            return get_installation_token(repo.installation_id, db)
        else:
            from app.core.config import settings
            tokens = settings.github.tokens
            if tokens and tokens[0]:
                return tokens[0]
        return None
    
    @staticmethod
    def _run_git(cwd: Path, args: List[str]) -> str:
        """Run a git command."""
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    
    def run_git(self, args: List[str]) -> str:
        """Run a git command in this repository."""
        return self._run_git(self.repo_path, args)
    
    def get_parent_commit(self, sha: str) -> Optional[str]:
        """Get the parent commit SHA."""
        try:
            return self.run_git(["rev-parse", f"{sha}^"])
        except subprocess.CalledProcessError:
            return None
