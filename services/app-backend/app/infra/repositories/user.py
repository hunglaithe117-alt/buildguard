"""Repository for users (infra layer)."""

from typing import Optional

from bson import ObjectId

from app.domain.entities import User
from app.infra.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db):
        super().__init__(db, "users", User)
        self.collection.create_index("username", unique=True)
        self.collection.create_index("email", unique=True)

    def find_by_username(self, username: str) -> Optional[User]:
        return self.find_one({"username": username})

    def find_by_email(self, email: str) -> Optional[User]:
        return self.find_one({"email": email})


__all__ = ["UserRepository"]
