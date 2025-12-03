from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from .base import BaseEntity, PyObjectId


class IngestionSourceType(str, Enum):
    GITHUB = "github"
    CSV = "csv"


class IngestionStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DatasetImportJob(BaseEntity):
    user_id: PyObjectId
    source_type: IngestionSourceType
    status: IngestionStatus = IngestionStatus.QUEUED

    # Configuration
    repo_url: Optional[str] = None
    dataset_template_id: Optional[PyObjectId] = None
    max_builds: Optional[int] = None
    csv_content: Optional[str] = None  # For small CSVs or stored content
    csv_file_path: Optional[str] = None  # For larger files stored on disk
    # References to selected FeatureDefinition documents
    selected_features: Optional[list[PyObjectId]] = None
    extractor_config: Optional[Dict[str, Any]] = None

    # Results
    builds_imported: int = 0
    logs_downloaded: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    metadata: Dict[str, Any] = {}
