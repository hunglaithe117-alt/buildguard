from typing import List, Dict, Optional
from .base import BaseEntity, PyObjectId


class DatasetTemplate(BaseEntity):
    """
    Dataset template (e.g., TravisTorrent, GHTorrent, Internal Standard).
    Contains a list of features that this dataset typically has or requires.
    """

    name: str
    description: Optional[str] = None

    # List of Feature IDs (referencing features collection)
    feature_ids: List[PyObjectId] = []

    # Default mapping suggestion: { "feature_key": "standard_csv_column_name" }
    # Helps auto-map if the CSV follows the standard (e.g., TravisTorrent format)
    default_mapping: Dict[str, str] = {}

    class Config:
        collection_name = "dataset_templates"
        arbitrary_types_allowed = True
