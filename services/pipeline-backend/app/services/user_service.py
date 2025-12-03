"""User/account helper utilities for the pipeline service."""

from datetime import datetime
from typing import Optional, Tuple

from pymongo.database import Database

from buildguard_common.models.oauth_identity import OAuthIdentity
from buildguard_common.models.user import User
from buildguard_common.repositories.oauth_identity_repository import (
    OAuthIdentityRepository,
)
from buildguard_common.repositories.user_repository import UserRepository

PROVIDER_GITHUB = "github"


def upsert_github_identity(
    db: Database,
    *,
    github_user_id: str,
    email: str,
    name: Optional[str],
    access_token: str,
    refresh_token: Optional[str],
    token_expires_at: Optional[datetime],
    scopes: Optional[str],
    account_login: Optional[str] = None,
    account_name: Optional[str] = None,
    account_avatar_url: Optional[str] = None,
    connected_at: Optional[datetime] = None,
) -> Tuple[User, OAuthIdentity]:
    """
    Create or update a user + GitHub OAuth identity.
    Returns (user, identity).
    """
    user_repo = UserRepository(db)
    oauth_repo = OAuthIdentityRepository(db)

    # 1) Find existing identity by provider/external id
    identity = oauth_repo.find_one(
        {"provider": PROVIDER_GITHUB, "external_user_id": github_user_id}
    )

    user: Optional[User] = None
    if identity:
        user = user_repo.find_by_id(identity.user_id)

    # 2) Fallback: find user by email
    if user is None:
        user = user_repo.find_by_email(email)

    # 3) Create user if needed
    if user is None:
        user = user_repo.insert_one(
            User(
                email=email,
                name=name,
                role="user",
            )
        )

    # 4) Upsert identity
    identity_payload = {
        "user_id": user.id,
        "provider": PROVIDER_GITHUB,
        "external_user_id": github_user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expires_at": token_expires_at,
        "scopes": scopes,
        "account_login": account_login,
        "account_name": account_name,
        "account_avatar_url": account_avatar_url,
        "connected_at": connected_at or datetime.utcnow(),
    }

    if identity:
        identity = oauth_repo.update(identity.id, identity_payload)
    else:
        identity = oauth_repo.insert_one(OAuthIdentity(**identity_payload))

    return user, identity


__all__ = ["upsert_github_identity"]
