"""GitHub App authentication utilities."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

import httpx
from jose import jwt

from .github_exceptions import GithubConfigurationError


def load_private_key(raw: str) -> str:
    """Load private key from string or file path."""
    if "BEGIN PRIVATE KEY" in raw:
        return raw.replace("\\n", "\n")
    path = Path(raw.strip().strip('"'))
    if path.exists():
        return path.read_text()
    raise GithubConfigurationError(
        "GITHUB_APP_PRIVATE_KEY must be a PEM string or path to a private key file",
    )


def generate_jwt(app_id: str, private_key: str) -> str:
    """Generate a JWT for GitHub App authentication."""
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": app_id,
    }
    pem = load_private_key(private_key)
    return jwt.encode(payload, pem, algorithm="RS256")


def request_installation_token(
    jwt_token: str, installation_id: str, api_url: str = "https://api.github.com"
) -> Tuple[str, datetime]:
    """Request an installation access token from GitHub."""
    url = f"{api_url.rstrip('/')}/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
    }
    response = httpx.post(url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    token = data.get("token")
    expires_at_raw = data.get("expires_at")
    expires_at = (
        datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
        if expires_at_raw
        else None
    )
    if not token or not expires_at:
        raise GithubConfigurationError(
            "GitHub installation token response missing token or expires_at"
        )
    return token, expires_at


def get_installation_token(
    app_id: str,
    private_key: str,
    installation_id: str,
    redis_client: Any,
    db: Any = None,
    api_url: str = "https://api.github.com",
) -> str:
    """
    Get an installation token, using Redis cache if available.

    Args:
        app_id: GitHub App ID
        private_key: GitHub App Private Key
        installation_id: Installation ID to get token for
        redis_client: Redis client instance for caching
        db: Optional MongoDB database to check installation status
        api_url: GitHub API URL
    """
    if not installation_id:
        raise GithubConfigurationError(
            "Installation id is required to generate a GitHub App token"
        )

    if db is not None:
        # Check if installation is valid in DB
        installation_doc = db.github_installations.find_one(
            {"installation_id": installation_id}
        )
        if installation_doc:
            if installation_doc.get("revoked_at") or installation_doc.get(
                "uninstalled_at"
            ):
                raise GithubConfigurationError(
                    f"GitHub App installation {installation_id} has been uninstalled. "
                    "User needs to reinstall the app."
                )
            if installation_doc.get("suspended_at"):
                raise GithubConfigurationError(
                    f"GitHub App installation {installation_id} is suspended."
                )

    redis_key = f"github_installation_token:{installation_id}"

    if redis_client:
        cached_token = redis_client.get(redis_key)
        if cached_token:
            # Redis returns bytes, decode if needed
            if isinstance(cached_token, bytes):
                return cached_token.decode("utf-8")
            return cached_token

    jwt_token = generate_jwt(app_id, private_key)
    token, expires_at = request_installation_token(jwt_token, installation_id, api_url)

    if redis_client:
        now = datetime.now(timezone.utc)
        ttl = int((expires_at - now).total_seconds() - 60)
        if ttl > 0:
            redis_client.set(redis_key, token, ex=ttl)

    return token


def clear_installation_token(installation_id: str, redis_client: Any) -> None:
    """Remove cached installation token when app is uninstalled or suspended."""
    if redis_client:
        redis_client.delete(f"github_installation_token:{installation_id}")
