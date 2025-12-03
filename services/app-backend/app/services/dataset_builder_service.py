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
        job = DatasetImportJob(
            user_id=ObjectId(user_id),
            source_type=payload.source_type,
            status=IngestionStatus.QUEUED,
            repo_url=payload.repo_url,
            dataset_template_id=(
                ObjectId(payload.dataset_template_id)
                if payload.dataset_template_id
                else None
            ),
            max_builds=payload.max_builds,
            csv_content=payload.csv_content,
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

    async def get_features_for_job(self, job_id: str) -> List[Dict[str, Any]]:
        job = self.get_job(job_id)
        if not job or not job.dataset_template_id:
            return []

        template_doc = self.db["dataset_templates"].find_one(
            {"_id": job.dataset_template_id}
        )
        if not template_doc:
            return []

        template = DatasetTemplate(**template_doc)

        # Fetch all features referenced in the template
        feature_ids = [f.feature_definition_id for f in template.features]

        features_cursor = self.db["feature_definitions"].find(
            {"_id": {"$in": feature_ids}}
        )

        features = []
        for doc in features_cursor:
            feat = FeatureDefinition(**doc)
            features.append(feat.dict(by_alias=True))

        return features

    async def start_extraction(
        self,
        job_id: str,
        selected_features: List[str],
        extractor_config: Dict[str, Any],
    ) -> None:
        # Update job with selection
        self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "selected_features": selected_features,
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

        celery_app.send_task(
            "pipeline.tasks.dataset_import.trigger_extraction_for_job",
            args=[job_id],
            queue="ingestion",
        )
