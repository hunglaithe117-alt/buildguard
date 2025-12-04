from datetime import datetime
from typing import Any, Dict, Optional

from .base import BaseEntity, PyObjectId


class WorkflowRunRaw(BaseEntity):
    repo_id: PyObjectId
    workflow_run_id: int
    head_sha: str
    run_number: int
    status: str
    conclusion: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    raw_payload: Dict[str, Any]
    log_fetched: bool = False
    log_expired: bool = False
