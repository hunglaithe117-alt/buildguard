import logging
from typing import Any, Dict, Optional, List, Type
from pymongo.database import Database

from app.domain.entities import BuildSample, ImportedRepository
from app.services.extracts.git_feature_extractor import GitHistoryExtractor
from app.services.extracts.base import BaseExtractor
from app.services.extracts.build_log_extractor import BuildLogExtractor
from app.services.extracts.github_discussion_extractor import GitHubApiExtractor
from app.services.extracts.repo_snapshot_extractor import RepoSnapshotExtractor
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
        self.extractors: Dict[str, BaseExtractor] = {
            FeatureSourceType.GIT_HISTORY: GitHistoryExtractor(db),
            FeatureSourceType.BUILD_LOG: BuildLogExtractor(db),
            FeatureSourceType.REPO_SNAPSHOT: RepoSnapshotExtractor(db),
            FeatureSourceType.GITHUB_API: GitHubApiExtractor(db),
            # Add other extractors here
        }
        # Cache for features per commit/run to avoid re-running for every row
        self._cache: Dict[str, Dict[str, Any]] = {}

    def extract_row(
        self,
        dataset: TrainingDataset,
        row: Dict[str, Any],
        repo: ImportedRepository,
        commit_sha: str,
        feature_definitions: Dict[str, FeatureDefinition],
        workflow_run_id: Optional[int] = None,  # Passed if available
    ) -> Dict[str, Any]:
        """
        Extract features for a single row based on dataset mapping configuration.
        """
        extracted_features = {}

        # Identify which extractors are needed for this row
        needed_sources = set()
        for mapping in dataset.mappings:
            if mapping.source_type in self.extractors:
                needed_sources.add(mapping.source_type)

        # Pre-fetch/Cache features from needed extractors
        context_features = {}

        # Create a temporary BuildSample for extractors
        # Some extractors might need more info (like run_id for logs)
        temp_sample = BuildSample(
            repo_id=repo.id,
            workflow_run_id=workflow_run_id if workflow_run_id else 0,
            tr_original_commit=commit_sha,
        )

        for source_type in needed_sources:
            extractor = self.extractors[source_type]
            # Cache key depends on source type
            # Git features depend on commit
            # Log features depend on run_id
            if source_type == FeatureSourceType.GIT_HISTORY:
                cache_key = f"{source_type}_{repo.id}_{commit_sha}"
            elif source_type == FeatureSourceType.BUILD_LOG:
                cache_key = f"{source_type}_{repo.id}_{workflow_run_id}"
            elif source_type == FeatureSourceType.GITHUB_API:
                cache_key = (
                    f"{source_type}_{repo.id}_{commit_sha}_{workflow_run_id}"
                )
            else:
                cache_key = f"{source_type}_{repo.id}_{commit_sha}"

            if cache_key in self._cache:
                context_features[source_type] = self._cache[cache_key]
            else:
                # Run extraction
                # Note: BuildLogExtractor needs workflow_run object ideally, but we might pass just IDs
                # For now, we assume extractors can work with BuildSample + Repo
                try:
                    features = extractor.extract(temp_sample, repo=repo)
                    self._cache[cache_key] = features
                    context_features[source_type] = features
                except Exception as e:
                    logger.error(f"Failed to run extractor {source_type}: {e}")
                    context_features[source_type] = {}

        for mapping in dataset.mappings:
            feature_def = feature_definitions.get(mapping.feature_key)
            if not feature_def:
                continue

            value = None

            # 1. CSV Mapping (Highest Priority if configured)
            if mapping.source_type == FeatureSourceType.MANUAL_UPLOAD:
                if mapping.csv_column and mapping.csv_column in row:
                    value = row[mapping.csv_column]
                    value = self._convert_type(value, feature_def.data_type)

            # 2. Extractor Mapping
            elif mapping.source_type in self.extractors:
                source_data = context_features.get(mapping.source_type, {})

                # Determine key to look up in source_data
                # Use extraction_config if available, else feature key
                lookup_key = feature_def.key
                if feature_def.extraction_config:
                    # e.g. {"git_key": "git_diff_src_churn"} or {"log_key": "tr_log_num_jobs"}
                    # We can standardize on a "key" field in config
                    lookup_key = feature_def.extraction_config.get(
                        "key", feature_def.key
                    )

                if lookup_key in source_data:
                    value = source_data[lookup_key]

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
