"""
Shared resources for feature extraction.

This module provides resource managers that can be shared across
multiple feature extractors to avoid redundant operations.
"""

from .git_repo import GitRepoResource
from .build_logs import BuildLogResource
from .github_client import GitHubClientResource

__all__ = [
    "GitRepoResource",
    "BuildLogResource",
    "GitHubClientResource",
]
