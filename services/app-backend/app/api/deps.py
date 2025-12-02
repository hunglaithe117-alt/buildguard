"""Common dependency aliases for API endpoints."""

from app.database.mongo import get_db
from app.middleware.auth import (
    get_current_user,
    get_current_user_id,
    require_admin,
)

__all__ = [
    "get_db",
    "get_current_user",
    "get_current_user_id",
    "require_admin",
]
