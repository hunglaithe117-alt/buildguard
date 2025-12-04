"""
GitHub Client Resource Manager.

Provides shared access to GitHub API client for feature extraction.
"""

import logging
from contextlib import contextmanager
from typing import Optional, Generator, Any

from app.services.github.github_client import (
    get_app_github_client,
    get_public_github_client,
)

from ..base import ExtractionContext

logger = logging.getLogger(__name__)


class GitHubClientResource:
    """
    Manages access to GitHub API client.
    
    Usage:
        resource = GitHubClientResource.from_context(context)
        with resource.client() as gh:
            comments = gh.list_commit_comments(repo_name, sha)
    """
    
    CACHE_KEY = "github_client_resource"
    
    def __init__(
        self,
        installation_id: Optional[int],
        db,
    ):
        self.installation_id = installation_id
        self.db = db
    
    @contextmanager
    def client(self) -> Generator[Any, None, None]:
        """Get a GitHub client context manager."""
        if self.installation_id:
            with get_app_github_client(self.db, self.installation_id) as gh:
                yield gh
        else:
            with get_public_github_client() as gh:
                yield gh
    
    @classmethod
    def from_context(cls, context: ExtractionContext) -> "GitHubClientResource":
        """
        Get or create a GitHubClientResource from the extraction context.
        """
        # Check cache first
        if context.has_cache(cls.CACHE_KEY):
            cached = context.get_cache(cls.CACHE_KEY)
            if isinstance(cached, GitHubClientResource):
                return cached
        
        installation_id = None
        if context.repo:
            installation_id = context.repo.installation_id
        
        resource = cls(installation_id, context.db)
        context.set_cache(cls.CACHE_KEY, resource)
        return resource
