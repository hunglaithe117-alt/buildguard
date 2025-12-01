from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .base import BaseEntity, PyObjectId


class ScanJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ScanJob(BaseEntity):
    repo_id: PyObjectId = Field(...)
    build_id: PyObjectId = Field(...)
    commit_sha: str = Field(...)
    status: ScanJobStatus = Field(default=ScanJobStatus.PENDING)

    # Execution details
    worker_id: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    # Results
    sonar_component_key: Optional[str] = None
    error_message: Optional[str] = None
    logs: Optional[str] = None  # Could be a link to log file or short snippet

    # Pipeline Backend Fields (Worker)
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    last_worker_id: Optional[str] = None
    last_started_at: Optional[datetime] = None
    last_finished_at: Optional[datetime] = None
    repository_url: Optional[str] = None
    repo_slug: Optional[str] = None
    project_key: Optional[str] = None
    component_key: Optional[str] = None
    sonar_instance: Optional[str] = None
    s3_log_key: Optional[str] = None
    log_path: Optional[str] = None
    config_override: Optional[str] = None
    config_source: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda dt: dt.isoformat()}
