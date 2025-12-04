"""User entity - represents a user account in the database"""

from typing import Literal, Optional

from .base import BaseEntity


class User(BaseEntity):
    email: str
    name: Optional[str] = None
    role: Literal["admin", "user"] = "user"
