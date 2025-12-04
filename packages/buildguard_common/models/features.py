from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import Field
from .base import BaseEntity


class FeatureDataType(str, Enum):
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"
    CATEGORY = "category"


class FeatureSourceType(str, Enum):
    """Source buckets for feature values. Keep string values stable for persistence."""

    MANUAL_UPLOAD = "csv_mapped"  # From user-uploaded CSV/explicit mapping
    BUILD_LOG = "build_log_extract"  # From CI job/build logs
    GIT_HISTORY = "git_history_extract"  # From git lineage/diff over commits
    REPO_SNAPSHOT = (
        "repo_snapshot_extract"  # From repo checkout at a commit (SLOC, tests)
    )
    GITHUB_API = "github_api_extract"  # From GitHub REST/GraphQL (PR/issue/comments)
    DERIVED = "derived"  # Computed from other features
    METADATA = "metadata"  # Static identifiers (repo slug, commit SHA)


class Feature(BaseEntity):
    """
    Definition of a feature (metric) supported by the system.
    Replaces FeatureDefinition.
    """

    key: str = Field(..., description="Unique identifier, e.g., 'complexity'")
    name: str = Field(..., description="Display name, e.g., 'Cyclomatic Complexity'")
    description: Optional[str] = None

    data_type: FeatureDataType
    default_source: FeatureSourceType

    # Dependencies required to calculate this feature
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of feature keys that this feature depends on.",
    )

    # Additional metadata for calculation (if needed)
    extraction_config: Optional[Dict[str, Any]] = None

    is_active: bool = True

    class Config:
        collection_name = "features"
