"""Shim for GitHub App token handling (moved to infra)."""

from app.infra.github_app import (
    github_app_configured,
    get_installation_token,
    clear_installation_token,
)

__all__ = [
    "github_app_configured",
    "get_installation_token",
    "clear_installation_token",
]
