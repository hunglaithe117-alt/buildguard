from typing import List, Optional

from pymongo import ASCENDING

from buildguard_common.models.github_public_token import GithubPublicToken
from buildguard_common.repositories.base import BaseRepository


class GithubPublicTokenRepository(BaseRepository[GithubPublicToken]):
    """Repository for managing GitHub public tokens."""

    def __init__(self, db):
        super().__init__(db, "github_public_tokens", GithubPublicToken)
        self._ensure_indexes()

    def _ensure_indexes(self):
        self.collection.create_index([("token", ASCENDING)], unique=True)
        self.collection.create_index("type")
        self.collection.create_index("disabled")

    def find_available_tokens(self) -> List[GithubPublicToken]:
        """Find all non-disabled tokens."""
        cursor = self.collection.find({"disabled": {"$ne": True}})
        return [self._to_model(doc) for doc in cursor]

    def find_by_token(self, token: str) -> Optional[GithubPublicToken]:
        return self.find_one({"token": token})

    def upsert_token(self, token: GithubPublicToken) -> GithubPublicToken:
        """Insert or update a token."""
        doc = token.model_dump(by_alias=True, exclude_none=True)
        # Remove _id if present to avoid immutable field error on update
        doc.pop("_id", None)

        self.collection.update_one({"token": token.token}, {"$set": doc}, upsert=True)
        return self.find_by_token(token.token)
