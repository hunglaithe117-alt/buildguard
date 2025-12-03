from enum import Enum
from typing import Optional
from pydantic import Field
from .base import BaseEntity


class FeatureDataType(str, Enum):
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"
    CATEGORY = "category"


class FeatureSourceType(str, Enum):
    METADATA = "metadata"  # Basic info (Repo name, Commit hash)
    CSV_MAPPED = "csv_mapped"  # Directly from uploaded CSV column
    GIT_EXTRACT = "git_extract"  # Calculated from Git (Diff, Blame)
    BUILD_LOG_EXTRACT = "build_log_extract"  # Extracted from build logs
    REPO_SNAPSHOT_EXTRACT = "repo_snapshot_extract"  # Extracted from repo snapshot
    DERIVED = "derived"  # Calculated from other features


class FeatureDefinition(BaseEntity):
    """
    Definition of a feature (metric) supported by the system.
    Example: Cyclomatic Complexity, Lines of Code, Build Duration.
    """

    key: str = Field(..., description="Unique identifier, e.g., 'complexity'")
    name: str = Field(..., description="Display name, e.g., 'Cyclomatic Complexity'")
    description: Optional[str] = None

    data_type: FeatureDataType

    # Default source suggestion for User
    default_source: FeatureSourceType

    # Additional metadata for calculation (if needed)
    # E.g., corresponding SonarQube metric key
    extraction_config: Optional[dict] = None

    is_active: bool = True

    class Config:
        collection_name = "feature_definitions"
