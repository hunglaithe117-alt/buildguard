from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from .base import BaseEntity
from .feature import FeatureSourceType


class DatasetStatus(str, Enum):
    PENDING = "PENDING"  # Created, mapping not finished
    READY_TO_PROCESS = "READY"  # Mapping finished, waiting to run
    PROCESSING = "PROCESSING"  # Running
    COMPLETED = "COMPLETED"  # Finished
    FAILED = "FAILED"


class FieldMapping(BaseModel):
    """
    Rule to get data for a specific feature in this dataset.
    """

    feature_key: str  # References FeatureDefinition

    source_type: FeatureSourceType  # Data source for this instance (CSV or Extract?)

    # If source is CSV_MAPPED -> Column name in CSV file
    csv_column: Optional[str] = None

    # Clean/transform config (if any)
    transform_rule: Optional[str] = None  # E.g., "normalize", "fill_zero"


class TrainingDataset(BaseEntity):
    """
    Represents a single data import/upload by the User.
    """

    name: str
    description: Optional[str] = None

    # ID of the selected Template (e.g., TravisTorrent Template)
    template_id: Optional[str] = None

    # File paths
    raw_file_path: Optional[str] = None
    processed_file_path: Optional[str] = None

    # --- IDENTITY MAPPING (REQUIRED) ---
    # User must specify which CSV columns correspond to Repo and Commit
    repo_column_name: Optional[str] = None
    commit_column_name: Optional[str] = None
    # -----------------------------------

    # Mapping configuration for the remaining features
    mappings: List[FieldMapping] = []

    status: DatasetStatus = DatasetStatus.PENDING

    # Quick stats (row count, detected columns)
    stats: Dict[str, Any] = Field(default_factory=dict)

    error_details: Optional[str] = None

    class Config:
        collection_name = "training_datasets"
