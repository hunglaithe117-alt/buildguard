from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from .base import BaseEntity, PyObjectId


class ScanCollectionStatus(str, Enum):
    QUEUED = "queued"
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class RepositoryScan(BaseEntity):
    project_id: PyObjectId
    sonar_project_key: str
    sonar_config: Optional[str] = None  # Content of sonar-project.properties

    status: ScanCollectionStatus = ScanCollectionStatus.QUEUED

    # Statistics
    total_commits: int = 0
    processed_commits: int = 0
    failed_commits: int = 0

    # Metrics
    metrics: List[str] = []

    last_scanned_at: Optional[datetime] = None
    last_error: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = {}
