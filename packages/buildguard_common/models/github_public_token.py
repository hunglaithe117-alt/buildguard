from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GithubPublicToken(BaseModel):
    """
    Represents a GitHub API token (PAT or OAuth) stored in the database.
    Used for public repository access and rate limit management.
    """

    token: str = Field(..., description="The actual token string")
    type: str = Field(default="pat", description="Token type: 'pat' or 'oauth'")
    remaining: int = Field(default=5000, description="Remaining rate limit")
    reset_time: float = Field(default=0.0, description="Rate limit reset timestamp")
    disabled: bool = Field(default=False, description="Whether the token is disabled")
    disabled_at: Optional[float] = Field(None, description="Timestamp when disabled")
    added_at: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    last_used: Optional[float] = Field(None, description="Timestamp when last used")
    id: Optional[str] = Field(None, alias="_id", description="MongoDB ID")

    class Config:
        populate_by_name = True
