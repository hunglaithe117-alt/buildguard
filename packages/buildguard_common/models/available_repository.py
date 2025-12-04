"""Available repository entity - caches repos available to user"""

from bson import ObjectId
from typing import Optional

from .base import BaseEntity, PyObjectId


class AvailableRepository(BaseEntity):
    user_id: PyObjectId  # The user who can see this repo
    full_name: str
    github_id: int
    private: bool
    html_url: str
    description: Optional[str] = None
    default_branch: str
    installation_id: Optional[str] = None  # If accessible via App
    imported: bool = False
