from typing import Any, Dict, Optional

from pydantic import Field

from .base import BaseEntity, PyObjectId


class EnrichedDatasetSample(BaseEntity):
    """
    Row-level data produced by dataset enrichment.
    Holds arbitrary feature values chosen by the user (not limited to a fixed template).
    """

    dataset_id: PyObjectId
    repo_id: Optional[PyObjectId] = None
    commit_sha: Optional[str] = None

    # Arbitrary feature key/value pairs for this dataset row
    features: Dict[str, Any] = Field(default_factory=dict)

    # Original row payload (if any) to help trace back
    source_row: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        collection_name = "dataset_samples"
