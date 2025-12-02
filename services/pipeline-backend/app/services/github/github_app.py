from __future__ import annotations

from app.core.config import settings
from app.core.redis import get_redis
from buildguard_common.github_auth import (
    get_installation_token as common_get_token,
    clear_installation_token as common_clear_token,
)


def get_installation_token(installation_id: str | None = None, db=None) -> str:
    return common_get_token(
        app_id=settings.github.app_id,
        private_key=settings.github.private_key,
        installation_id=installation_id,
        redis_client=get_redis(),
        db=db,
        api_url=settings.github.api_url,
    )


def clear_installation_token(installation_id: str) -> None:
    """Remove cached installation token when app is uninstalled or suspended."""
    common_clear_token(installation_id, get_redis())


def github_app_configured() -> bool:
    return bool(settings.github.app_id and settings.github.private_key)
