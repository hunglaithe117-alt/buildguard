"""Shared utilities for BuildGuard services."""

from .logger import OTelJSONFormatter, setup_logging
from .mongo import get_client, get_database, yield_database
from .tasks import MongoTask
from .github_exceptions import (
    GithubError,
    GithubConfigurationError,
    GithubRateLimitError,
    GithubRetryableError,
    GithubAllRateLimitError,
)
from .github_client import GitHubClient, GitHubTokenPool

__all__ = [
    "OTelJSONFormatter",
    "setup_logging",
    "get_client",
    "get_database",
    "yield_database",
    "MongoTask",
    "GithubError",
    "GithubConfigurationError",
    "GithubRateLimitError",
    "GithubRetryableError",
    "GithubAllRateLimitError",
    "GitHubClient",
    "GitHubTokenPool",
]
