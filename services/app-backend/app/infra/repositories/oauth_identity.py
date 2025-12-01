"""Repository for OAuth identities (infra layer)."""

from typing import Optional

from bson import ObjectId

from app.domain.entities import OAuthIdentity, User
from app.infra.repositories.base import BaseRepository


class OAuthIdentityRepository(BaseRepository[OAuthIdentity]):
    def __init__(self, db):
        super().__init__(db, "oauth_identities", OAuthIdentity)

    def find_by_user_and_provider(self, user_id: str | ObjectId, provider: str) -> Optional[OAuthIdentity]:
        return self.find_one({"user_id": self._to_object_id(user_id), "provider": provider})

    def find_by_user(self, user_id: str | ObjectId) -> Optional[OAuthIdentity]:
        return self.find_one({"user_id": self._to_object_id(user_id)})

    def get_user_identity(self, user: User, provider: str = "github") -> Optional[OAuthIdentity]:
        return self.find_one({"user_id": user.id, "provider": provider})


__all__ = ["OAuthIdentityRepository"]
