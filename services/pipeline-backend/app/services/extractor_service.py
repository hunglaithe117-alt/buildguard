import logging
from typing import Any, Dict, Optional, List
from pymongo.database import Database

from app.domain.entities import BuildSample, ImportedRepository
from app.services.extracts.git_feature_extractor import GitFeatureExtractor
from buildguard_common.models.dataset import (
    TrainingDataset,
    FieldMapping,
    FeatureSourceType,
)
from buildguard_common.models.feature import FeatureDefinition

logger = logging.getLogger(__name__)


class ExtractorService:
    def __init__(self, db: Database):
        self.db = db
        self.git_extractor = GitFeatureExtractor(db)
        # Cache for Git features per commit to avoid re-running for every row if multiple rows share a commit
        self._git_cache: Dict[str, Dict[str, Any]] = {}

    def extract_row(
        self,
        dataset: TrainingDataset,
        row: Dict[str, Any],
        repo: ImportedRepository,
        commit_sha: str,
        feature_definitions: Dict[str, FeatureDefinition],
    ) -> Dict[str, Any]:
        """
        Extract features for a single row based on dataset mapping configuration.
        """
        extracted_features = {}

        # Pre-fetch Git features if needed by any mapping
        git_features = {}
        needs_git = any(
            m.source_type == FeatureSourceType.GIT_EXTRACT for m in dataset.mappings
        )

        if needs_git:
            cache_key = f"{repo.id}_{commit_sha}"
            if cache_key in self._git_cache:
                git_features = self._git_cache[cache_key]
            else:
                # Create a temporary BuildSample for the extractor
                # The extractor needs tr_original_commit
                temp_sample = BuildSample(
                    repo_id=repo.id,
                    workflow_run_id=0,  # Dummy
                    tr_original_commit=commit_sha,
                )
                git_features = self.git_extractor.extract(temp_sample, repo=repo)
                self._git_cache[cache_key] = git_features

        for mapping in dataset.mappings:
            feature_def = feature_definitions.get(mapping.feature_key)
            if not feature_def:
                continue

            value = None

            if mapping.source_type == FeatureSourceType.CSV_MAPPED:
                if mapping.csv_column and mapping.csv_column in row:
                    value = row[mapping.csv_column]
                    # Basic type conversion
                    value = self._convert_type(value, feature_def.data_type)

            elif mapping.source_type == FeatureSourceType.GIT_EXTRACT:
                # Map from GitFeatureExtractor output using extraction_config
                if feature_def.extraction_config:
                    git_key = feature_def.extraction_config.get("git_key")
                    if git_key and git_key in git_features:
                        value = git_features[git_key]
                else:
                    # Fallback: try using the feature key itself if no config
                    if feature_def.key in git_features:
                        value = git_features[feature_def.key]

            # Store in result dict
            extracted_features[feature_def.key] = value

        return extracted_features

    def _convert_type(self, value: Any, target_type: str) -> Any:
        if value is None or value == "":
            return None
        try:
            if target_type == "integer":
                return int(float(value))  # Handle "1.0" strings
            elif target_type == "float":
                return float(value)
            elif target_type == "boolean":
                return str(value).lower() in ("true", "1", "yes")
            elif target_type == "string":
                return str(value)
        except Exception:
            return value
        return value
