from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo.database import Database

from app.dtos.ingestion import IngestionJobCreateRequest
from buildguard_common.models import (
    DatasetImportJob,
    IngestionStatus,
    IngestionSourceType,
)
from app.celery_app import celery_app
from buildguard_common.models.feature import FeatureDefinition
from buildguard_common.models.dataset_template import DatasetTemplate


class DatasetBuilderService:
    def __init__(self, db: Database):
        self.db = db
        self.collection = db["dataset_import_jobs"]

    def create_job(
        self, user_id: str, payload: IngestionJobCreateRequest
    ) -> DatasetImportJob:
        template_id = None
        if payload.dataset_template_id:
            try:
                template_id = ObjectId(payload.dataset_template_id)
            except Exception:
                template_id = None

        job = DatasetImportJob(
            user_id=ObjectId(user_id),
            source_type=payload.source_type,
            status=IngestionStatus.QUEUED,
            repo_url=payload.repo_url,
            dataset_template_id=template_id,
            max_builds=payload.max_builds,
            csv_content=payload.csv_content,
            selected_features=payload.selected_features,
            created_at=datetime.utcnow(),
        )

        result = self.collection.insert_one(job.dict(by_alias=True))
        job.id = result.inserted_id

        # Trigger Celery task
        celery_app.send_task(
            "pipeline.tasks.dataset_import.import_dataset",
            args=[str(job.id)],
            queue="ingestion",
        )

        return job

    def list_jobs(
        self, user_id: str, skip: int = 0, limit: int = 20
    ) -> List[DatasetImportJob]:
        cursor = (
            self.collection.find({"user_id": ObjectId(user_id)})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return [DatasetImportJob(**doc) for doc in cursor]

    def get_job(self, job_id: str) -> Optional[DatasetImportJob]:
        doc = self.collection.find_one({"_id": ObjectId(job_id)})
        if doc:
            return DatasetImportJob(**doc)
        return None
        return None

    def _resolve_feature_ids(self, feature_keys: List[str]) -> List[ObjectId]:
        """
        Map selected feature keys to their FeatureDefinition ObjectIds.
        Raises ValueError if any key is missing so the client can surface the issue.
        """
        if not feature_keys:
            return []

        cursor = self.db["feature_definitions"].find(
            {"key": {"$in": feature_keys}}, {"_id": 1, "key": 1}
        )
        key_to_id = {doc["key"]: doc["_id"] for doc in cursor}
        missing = [k for k in feature_keys if k not in key_to_id]
        if missing:
            raise ValueError(f"Unknown feature keys: {missing}")
        return list(key_to_id.values())

    async def get_features_for_job(self, job_id: str) -> List[Dict[str, Any]]:
        job = self.get_job(job_id)
        if not job or not job.dataset_template_id:
            return []

        template_doc = self.db["dataset_templates"].find_one(
            {"_id": ObjectId(job.dataset_template_id)}
        )
        if not template_doc:
            return []

        template = DatasetTemplate(**template_doc)

        feature_keys = getattr(template, "feature_keys", None) or []
        if not feature_keys:
            return []

        features_cursor = self.db["feature_definitions"].find(
            {"key": {"$in": feature_keys}}
        )

        features: List[Dict[str, Any]] = []
        for doc in features_cursor:
            feat = FeatureDefinition(**doc)
            features.append(
                {
                    "key": feat.key,
                    "name": feat.name,
                    "description": feat.description,
                    "default_source": feat.default_source,
                    "is_active": feat.is_active,
                }
            )

        # Preserve template order
        key_order = {k: i for i, k in enumerate(feature_keys)}
        features.sort(key=lambda f: key_order.get(f["key"], len(key_order)))
        return features

    async def start_extraction(
        self,
        job_id: str,
        selected_features: List[str],
        extractor_config: Dict[str, Any],
    ) -> None:
        feature_ids = self._resolve_feature_ids(selected_features)

        # Update job with selection
        self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "selected_features": feature_ids,
                    "extractor_config": extractor_config,
                    "status": IngestionStatus.PROCESSING,  # Move to processing
                }
            },
        )

        # Trigger extraction tasks
        # Note: In the new flow, import_dataset (stage 1) should have finished
        # and populated build_samples with raw data.
        # Now we trigger the extraction pipeline for each build sample.
        # However, for simplicity/MVP, we might just trigger a task that iterates
        # over builds and queues extraction.

            queue="ingestion",
        )

    def list_available_features(self) -> List[Dict[str, Any]]:
        """
        List all available features.
        
        Note: Ideally this should come from the registry in pipeline-backend.
        For now, we return the list of features we just refactored.
        """
        # This list mirrors the registry in pipeline-backend
        features = [
            # Git Features
            {"name": "git_prev_commit_resolution_status", "source": "git_history", "description": "Status of the previous commit"},
            {"name": "git_prev_built_commit", "source": "git_history", "description": "SHA of the previous built commit"},
            {"name": "tr_prev_build", "source": "git_history", "description": "ID of the previous build"},
            {"name": "git_all_built_commits", "source": "git_history", "description": "List of all built commits"},
            {"name": "git_num_all_built_commits", "source": "git_history", "description": "Number of built commits"},
            {"name": "gh_team_size", "source": "git_history", "description": "Size of the core team"},
            {"name": "gh_by_core_team_member", "source": "git_history", "description": "Whether the commit is by a core team member"},
            {"name": "gh_num_commits_on_files_touched", "source": "git_history", "description": "Number of commits on touched files"},
            {"name": "git_diff_src_churn", "source": "git_history", "description": "Source code churn"},
            {"name": "git_diff_test_churn", "source": "git_history", "description": "Test code churn"},
            {"name": "gh_diff_files_added", "source": "git_history", "description": "Number of files added"},
            {"name": "gh_diff_files_deleted", "source": "git_history", "description": "Number of files deleted"},
            {"name": "gh_diff_files_modified", "source": "git_history", "description": "Number of files modified"},
            {"name": "gh_diff_tests_added", "source": "git_history", "description": "Number of tests added"},
            {"name": "gh_diff_tests_deleted", "source": "git_history", "description": "Number of tests deleted"},
            {"name": "gh_diff_src_files", "source": "git_history", "description": "Number of source files changed"},
            {"name": "gh_diff_doc_files", "source": "git_history", "description": "Number of doc files changed"},
            {"name": "gh_diff_other_files", "source": "git_history", "description": "Number of other files changed"},
            
            # Build Log Features
            {"name": "tr_jobs", "source": "build_log", "description": "List of job IDs"},
            {"name": "tr_build_id", "source": "build_log", "description": "Build ID"},
            {"name": "tr_build_number", "source": "build_log", "description": "Build Number"},
            {"name": "tr_original_commit", "source": "build_log", "description": "Original Commit SHA"},
            {"name": "tr_log_lan_all", "source": "build_log", "description": "Languages detected"},
            {"name": "tr_log_frameworks_all", "source": "build_log", "description": "Frameworks detected"},
            {"name": "tr_log_num_jobs", "source": "build_log", "description": "Number of jobs"},
            {"name": "tr_log_tests_run_sum", "source": "build_log", "description": "Total tests run"},
            {"name": "tr_log_tests_failed_sum", "source": "build_log", "description": "Total tests failed"},
            {"name": "tr_log_tests_skipped_sum", "source": "build_log", "description": "Total tests skipped"},
            {"name": "tr_log_tests_ok_sum", "source": "build_log", "description": "Total tests passed"},
            {"name": "tr_log_tests_fail_rate", "source": "build_log", "description": "Test failure rate"},
            {"name": "tr_log_testduration_sum", "source": "build_log", "description": "Total test duration"},
            {"name": "tr_status", "source": "build_log", "description": "Build status"},
            {"name": "tr_duration", "source": "build_log", "description": "Build duration"},
        ]
        return features
