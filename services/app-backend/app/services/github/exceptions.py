"""Compatibility re-export of shared GitHub exception types."""

from buildguard_common.github_exceptions import (  # noqa: F401
    GithubError,
    GithubConfigurationError,
    GithubRateLimitError,
    GithubRetryableError,
    GithubAllRateLimitError,
)
