import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from bson import ObjectId
from git import Repo
from pymongo.database import Database

from app.models.entities.build_sample import BuildSample
from app.repositories.build_sample import BuildSampleRepository
from app.repositories.imported_repository import ImportedRepositoryRepository
from app.services.github.github_app import get_installation_token
from app.utils.locking import repo_lock

logger = logging.getLogger(__name__)

REPOS_DIR = Path("../repo-data/repos")

class DiffService:
    def __init__(self, db: Database):
        self.db = db
        self.build_sample_repo = BuildSampleRepository(db)
        self.repo_repo = ImportedRepositoryRepository(db)

    def compare_builds(
        self, repo_id: str, base_build_id: str, head_build_id: str
    ) -> Dict[str, Any]:
        base_build = self.build_sample_repo.find_by_id(ObjectId(base_build_id))
        head_build = self.build_sample_repo.find_by_id(ObjectId(head_build_id))

        if not base_build or not head_build:
            raise ValueError("One or both builds not found")

        if str(base_build.repo_id) != repo_id or str(head_build.repo_id) != repo_id:
            raise ValueError("Builds do not belong to the specified repository")

        # 1. Metric Deltas
        metrics_diff = self._calculate_metric_deltas(base_build, head_build)

        # 2. Git Diff (Files & Commits)
        git_diff = self._get_git_diff(repo_id, base_build, head_build)

        return {
            "base_build": self._serialize_build(base_build),
            "head_build": self._serialize_build(head_build),
            "metrics_diff": metrics_diff,
            "files_changed": git_diff.get("files", []),
            "commits": git_diff.get("commits", []),
        }

    def _calculate_metric_deltas(
        self, base: BuildSample, head: BuildSample
    ) -> Dict[str, Any]:
        deltas = {}
        # List of numeric metrics to compare
        metrics = [
            "git_diff_src_churn",
            "git_diff_test_churn",
            "gh_sloc",
            "gh_test_lines_per_kloc",
            "gh_test_cases_per_kloc",
            "gh_asserts_case_per_kloc",
            "gh_team_size",
            "gh_num_issue_comments",
            "gh_num_pr_comments",
            "gh_num_commit_comments",
            "gh_description_complexity",
        ]

        for metric in metrics:
            base_val = getattr(base, metric, 0) or 0
            head_val = getattr(head, metric, 0) or 0
            # Ensure they are numbers
            if isinstance(base_val, (int, float)) and isinstance(head_val, (int, float)):
                deltas[metric] = head_val - base_val
            else:
                deltas[metric] = 0

        return deltas

    def _get_git_diff(
        self, repo_id: str, base: BuildSample, head: BuildSample
    ) -> Dict[str, Any]:
        repo_obj = self.repo_repo.find_by_id(repo_id)
        if not repo_obj:
            return {}

        repo_path = REPOS_DIR / repo_id
        
        base_sha = base.tr_original_commit
        head_sha = head.tr_original_commit

        if not base_sha or not head_sha:
            return {}

        try:
            with repo_lock(repo_id):
                if not repo_path.exists():
                     # Should exist if builds were processed, but handle case
                     return {}
                
                git_repo = Repo(str(repo_path))
                
                # Ensure commits exist (fetch if needed)
                # We assume they exist if builds were processed.
                # If not, we might need to fetch.
                try:
                    git_repo.commit(base_sha)
                    git_repo.commit(head_sha)
                except Exception:
                    # Try fetch
                    self._fetch_repo(repo_path)
                
                # Get changed files
                # git diff --name-status base head
                diff_output = git_repo.git.diff("--name-status", base_sha, head_sha)
                files_changed = []
                for line in diff_output.splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        status = parts[0][0]
                        path = parts[-1]
                        files_changed.append({"status": status, "path": path})

                # Get commits in between
                # git log --pretty=format:"%H|%an|%s" base..head
                log_output = git_repo.git.log(
                    "--pretty=format:%H|%an|%s", f"{base_sha}..{head_sha}"
                )
                commits = []
                for line in log_output.splitlines():
                    parts = line.split("|", 2)
                    if len(parts) == 3:
                        commits.append({
                            "sha": parts[0],
                            "author": parts[1],
                            "message": parts[2]
                        })

                return {"files": files_changed, "commits": commits}

        except Exception as e:
            logger.error(f"Failed to get git diff: {e}")
            return {}

    def _fetch_repo(self, repo_path: Path):
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=repo_path,
            check=False,
            capture_output=True
        )

    def _serialize_build(self, build: BuildSample) -> Dict[str, Any]:
        # Helper to convert ObjectId and datetime to string/isoformat if needed
        # Pydantic model dump usually handles this, but for safety
        data = build.model_dump()
        data["id"] = str(data["id"])
        data["repo_id"] = str(data["repo_id"])
        if data.get("gh_build_started_at"):
            data["gh_build_started_at"] = data["gh_build_started_at"].isoformat()
        return data
