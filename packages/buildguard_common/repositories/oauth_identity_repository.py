"""Repository for OAuth identities (infra layer)."""

from typing import Optional, Union

from bson import ObjectId

from buildguard_common.models.oauth_identity import OAuthIdentity
from buildguard_common.models.user import User
from buildguard_common.repositories.base import BaseRepository, CollectionName


class OAuthIdentityRepository(BaseRepository[OAuthIdentity]):
    def __init__(self, db):
        super().__init__(db, CollectionName.OAUTH_IDENTITIES, OAuthIdentity)

    def find_by_user_and_provider(
        self, user_id: Union[str, ObjectId], provider: str
    ) -> Optional[OAuthIdentity]:
        return self.find_one(
            {"user_id": self._to_object_id(user_id), "provider": provider}
        )

    def find_by_user(self, user_id: Union[str, ObjectId]) -> Optional[OAuthIdentity]:
        return self.find_one({"user_id": self._to_object_id(user_id)})

    def get_user_identity(
        self, user: User, provider: str = "github"
    ) -> Optional[OAuthIdentity]:
        return self.find_one({"user_id": user.id, "provider": provider})


__all__ = ["OAuthIdentityRepository"]
