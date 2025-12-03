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
    """Source buckets for feature values. Keep string values stable for persistence."""

    MANUAL_UPLOAD = "csv_mapped"  # From user-uploaded CSV/explicit mapping
    BUILD_LOG = "build_log_extract"  # From CI job/build logs
    GIT_HISTORY = "git_history_extract"  # From git lineage/diff over commits
    REPO_SNAPSHOT = "repo_snapshot_extract"  # From repo checkout at a commit (SLOC, tests)
    GITHUB_API = "github_api_extract"  # From GitHub REST/GraphQL (PR/issue/comments)
    DERIVED = "derived"  # Computed from other features
    METADATA = "metadata"  # Static identifiers (repo slug, commit SHA)


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
    extraction_config: Optional[dict] = None

    is_active: bool = True

    class Config:
        collection_name = "feature_definitions"
