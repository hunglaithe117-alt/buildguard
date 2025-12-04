from typing import Optional
from pydantic import BaseModel, Field
from app.dtos.base import BaseResponse
from buildguard_common.models import IngestionSourceType, IngestionStatus


class IngestionJobCreateRequest(BaseModel):
    source_type: IngestionSourceType
    repo_url: Optional[str] = None
    dataset_template_id: Optional[str] = None
    max_builds: Optional[int] = Field(default=100, ge=1, le=1000)
    selected_features: Optional[list[str]] = None
    # For CSV, we might handle file upload separately, but if it's small content:
    csv_content: Optional[str] = None


class IngestionJobResponse(BaseResponse):
    source_type: IngestionSourceType
    status: IngestionStatus
    repo_url: Optional[str] = None
    dataset_template_id: Optional[str] = None
    max_builds: Optional[int] = None
    builds_imported: int
    logs_downloaded: int
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
