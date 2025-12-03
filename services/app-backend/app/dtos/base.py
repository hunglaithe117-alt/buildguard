"""Common DTO base classes."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from buildguard_common.models.base import PyObjectIdStr


class BaseResponse(BaseModel):
    """Shared response fields for API DTOs."""

    id: Optional[PyObjectIdStr] = Field(default=None, alias="_id")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
