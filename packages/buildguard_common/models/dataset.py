from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from .base import BaseEntity, PyObjectId
from .features import FeatureSourceType


class DatasetStatus(str, Enum):
    PENDING = "PENDING"  # Created, mapping not finished
    READY_TO_PROCESS = "READY"  # Mapping finished, waiting to run
    PROCESSING = "PROCESSING"  # Running
    COMPLETED = "COMPLETED"  # Finished
    FAILED = "FAILED"


class DatasetSource(str, Enum):
    CSV_UPLOAD = "csv_upload"
    GITHUB_IMPORT = "github_import"


class DatasetConfig(BaseModel):
    """Configuration for the data source."""

    # For GitHub Import
    repo_url: Optional[str] = None
    build_limit: Optional[int] = Field(default=100)

    # For CSV Upload
    file_path: Optional[str] = None
    # Mandatory mapping for the 3 required columns
    mandatory_mapping: Optional[Dict[str, str]] = Field(
        default=None,
        description="Internal map: {'tr_build_id': 'csv_col_1', 'gh_project_name': 'csv_col_2', ...}",
    )

    class Config:
        arbitrary_types_allowed = True


class FieldMapping(BaseModel):
    """
    Rule to get data for a specific feature in this dataset.
    """

    # Reference to features collection _id
    feature_id: PyObjectId = Field(
        ..., description="Reference to features collection _id"
    )
    feature_key: str  # Kept for UI display convenience

    source_type: FeatureSourceType  # MANUAL_UPLOAD (CSV) or SYSTEM_EXTRACT (Computed)

    # If source is MANUAL_UPLOAD -> Column name in CSV file
    csv_column: Optional[str] = None

    # Clean/transform config (if any)
    transform_rule: Optional[str] = None  # E.g., "normalize", "fill_zero"

    class Config:
        arbitrary_types_allowed = True


class TrainingDataset(BaseEntity):
    """
    Represents a single data import/upload by the User.
    """

    name: str
    description: Optional[str] = None

    # Data source type
    source_type: DatasetSource

    # Detailed configuration (File or Repo)
    config: DatasetConfig

    # ID of the selected Template (e.g., TravisTorrent Template)
    template_id: Optional[PyObjectId] = None

    # List of features user wants in the final dataset
    mappings: List[FieldMapping] = []

    status: DatasetStatus = DatasetStatus.PENDING

    # Quick stats (row count, detected columns)
    stats: Dict[str, Any] = Field(default_factory=dict)

    error_details: Optional[str] = None

    class Config:
        collection_name = "training_datasets"
