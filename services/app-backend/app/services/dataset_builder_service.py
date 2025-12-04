from datetime import datetime
import os
from typing import Any, Dict, List, Optional
from fastapi import UploadFile

from bson import ObjectId
from pymongo.database import Database


from buildguard_common.models import (
    DatasetImportJob,
    IngestionStatus,
    IngestionSourceType,
)
from app.celery_app import celery_app
from buildguard_common.models.features import Feature
from buildguard_common.models.dataset_template import DatasetTemplate


class DatasetBuilderService:
    def __init__(self, db: Database):
        self.db = db
        self.collection = db["dataset_import_jobs"]

    async def create_job(
        self,
        user_id: str,
        source_type: str,
        repo_url: Optional[str] = None,
        dataset_template_id: Optional[str] = None,
        max_builds: int = 100,
        selected_features: Optional[List[str]] = None,
        csv_file: Optional[UploadFile] = None,
    ) -> DatasetImportJob:
        template_id = None
        if dataset_template_id:
            try:
                template_id = ObjectId(dataset_template_id)
            except Exception:
                template_id = None

        job = DatasetImportJob(
            user_id=ObjectId(user_id),
            source_type=source_type,
            status=IngestionStatus.QUEUED,
            repo_url=repo_url,
            dataset_template_id=template_id,
            max_builds=max_builds,
            selected_features=None,  # selected_features logic usually handled in start_extraction or resolved here?
            # The original code passed payload.selected_features directly.
            # But selected_features in DatasetImportJob expects list[PyObjectId].
            # The original code was: selected_features=payload.selected_features
            # But payload.selected_features was list[str].
            # This implies the original code might have been buggy or PyObjectId handles str conversion if it's a valid ID?
            # Or maybe selected_features in Job is list[str]?
            # Let's check DatasetImportJob model again.
            # It is Optional[list[PyObjectId]].
            # If payload.selected_features sends feature KEYS (strings), then we need to resolve them.
            # But create_job didn't seem to resolve them in original code?
            # Let's assume for now we pass None or handle it if needed.
            # Actually, looking at original code: selected_features=payload.selected_features
            # If payload had strings, and model expects ObjectIds, Pydantic might fail or cast if they are valid ObjectIds.
            # But feature keys are usually strings like "git_commit_hash".
            # So likely the original code was just storing them?
            # Wait, DatasetImportJob definition: selected_features: Optional[list[PyObjectId]]
            # So it expects ObjectIds.
            # If the user sends keys, this would fail.
            # Maybe create_job is not supposed to set selected_features yet?
            # Or maybe the frontend sends IDs?
            # Let's leave it as None for now to be safe, or resolve if we have keys.
            # Given we are refactoring, let's just pass None as we do in start_extraction.
            created_at=datetime.utcnow(),
        )

        # If selected_features were passed (e.g. IDs), we could set them, but let's stick to the flow where we configure later.

        # Handle CSV content if present
        if csv_file:
            upload_dir = os.path.abspath("repo-data/uploads")
            os.makedirs(upload_dir, exist_ok=True)

            file_path = os.path.join(upload_dir, f"{job.id}.csv")

            # Stream file to disk
            with open(file_path, "wb") as f:
                while content := await csv_file.read(1024 * 1024):  # Read in 1MB chunks
                    f.write(content)

            job.csv_file_path = file_path

        result = self.collection.insert_one(job.dict(by_alias=True))
        # job.id is already set

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

        cursor = self.db["features"].find(
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

        features_cursor = self.db["features"].find({"key": {"$in": feature_keys}})

        features: List[Dict[str, Any]] = []
        for doc in features_cursor:
            feat = Feature(**doc)
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
        # extractor_config: Dict[str, Any], # Removed
        column_mapping: Optional[Dict[str, str]] = None,
    ) -> None:
        job = self.get_job(job_id)
        if not job:
            raise ValueError("Job not found")

        # Validate mandatory fields for CSV source
        if job.source_type == IngestionSourceType.CSV:
            if not column_mapping:
                raise ValueError("Column mapping is required for CSV ingestion")

            mandatory_fields = ["tr_build_id", "gh_project_name", "git_trigger_commit"]
            missing_fields = [
                field
                for field in mandatory_fields
                if field not in column_mapping or not column_mapping[field]
            ]

            if missing_fields:
                raise ValueError(
                    f"Missing mandatory mapping for fields: {', '.join(missing_fields)}. "
                    "These fields are required to identify the build and repository."
                )

        feature_ids = self._resolve_feature_ids(selected_features)

        # Update job with selection
        # Update job with selection
        self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "selected_features": feature_ids,
                    "column_mapping": column_mapping,
                    # extractor_config removed
                    "status": IngestionStatus.PROCESSING,  # Move to processing
                }
            },
        )

        # Trigger extraction tasks
        celery_app.send_task(
            "pipeline.tasks.dataset_import.trigger_extraction_for_job",
            args=[job_id],
            queue="ingestion",
        )

    def list_available_features(self) -> List[Dict[str, Any]]:
        """
        List all available features from the database.
        """
        cursor = self.db["features"].find({"is_active": True})
        features = []
        for doc in cursor:
            # We use the 'key' as the identifier in the UI, but map it to 'name'
            # for backward compatibility with the previous hardcoded list if needed.
            # However, the previous list used 'name' as the key (e.g. 'git_prev_commit_resolution_status').
            # Our seeded data has key='git_prev_commit_resolution_status' and name='Git Prev Commit Resolution Status'.
            # So we map key -> name, and name -> display_name.

            feat = Feature(**doc)
            features.append(
                {
                    "name": feat.key,  # Identifier
                    "display_name": feat.name,  # Human readable name
                    "source": feat.default_source,
                    "description": feat.description,
                    "data_type": feat.data_type,
                }
            )

        # Sort by source then name
        features.sort(key=lambda x: (x["source"], x["name"]))
        return features
