from pathlib import Path
import pandas as pd
from celery.utils.log import get_task_logger
from bson import ObjectId

from app.celery_app import celery_app
from app.core.config import settings
from buildguard_common.mongo import get_database
from buildguard_common.models.dataset import TrainingDataset, DatasetStatus
from buildguard_common.models.feature import FeatureDefinition
from app.repositories import ProjectsRepository, BuildSampleRepository
from app.services.extractor_service import ExtractorService
from app.models import ProjectStatus

logger = get_task_logger(__name__)


def _get_db():
    return get_database(settings.mongo.uri, settings.mongo.database)


@celery_app.task(bind=True, name="pipeline.process_dataset")
def process_dataset(self, dataset_id: str) -> dict:
    db = _get_db()
    dataset_coll = db.training_datasets
    feature_coll = db.feature_definitions
    projects_repo = ProjectsRepository(db)
    build_sample_repo = BuildSampleRepository(db)
    extractor_service = ExtractorService(db)

    # 1. Load Dataset
    dataset_doc = dataset_coll.find_one({"_id": ObjectId(dataset_id)})
    if not dataset_doc:
        logger.error(f"Dataset {dataset_id} not found")
        return {"status": "failed", "error": "Dataset not found"}

    dataset = TrainingDataset(**dataset_doc)

    # Update status to PROCESSING
    dataset_coll.update_one(
        {"_id": ObjectId(dataset_id)}, {"$set": {"status": DatasetStatus.PROCESSING}}
    )

    try:
        # 2. Load Feature Definitions
        # We need definitions to know types and extraction configs
        feature_defs = {}
        for doc in feature_coll.find():
            feat = FeatureDefinition(**doc)
            feature_defs[feat.key] = feat

        # 3. Read CSV
        if not dataset.raw_file_path or not Path(dataset.raw_file_path).exists():
            raise ValueError(f"File not found: {dataset.raw_file_path}")

        df = pd.read_csv(dataset.raw_file_path, dtype=str).fillna("")

        processed_count = 0
        errors = 0

        for _, row in df.iterrows():
            try:
                # 4. Resolve Identity
                repo_name = row.get(dataset.repo_column_name)
                commit_sha = row.get(dataset.commit_column_name)

                if not repo_name or not commit_sha:
                    continue

                # Find Repo ID
                # This assumes repo_name matches what we have in ImportedRepository
                # Or we might need a fuzzy search / mapping strategy later
                repo = projects_repo.find_by_slug(repo_name)
                if not repo:
                    # Try creating a placeholder or skipping?
                    # For now, let's skip if repo not found in our system
                    # OR we could try to find by URL if column is URL
                    continue

                # 5. Extract Features
                features = extractor_service.extract_row(
                    dataset, row.to_dict(), repo, commit_sha, feature_defs
                )

                # 6. Save BuildSample
                # Check if sample exists
                existing_sample = build_sample_repo.find_one(
                    {"repo_id": repo.id, "tr_original_commit": commit_sha}
                )

                if existing_sample:
                    build_sample_repo.update_one(
                        str(existing_sample.id), {"features": features}
                    )
                else:
                    # Create new sample
                    build_sample_repo.create(
                        {
                            "repo_id": repo.id,
                            "tr_original_commit": commit_sha,
                            "workflow_run_id": 0,  # Dummy
                            "features": features,
                            "status": "completed",
                        }
                    )

                processed_count += 1

            except Exception as e:
                logger.error(f"Error processing row: {e}")
                errors += 1

        # 7. Finish
        dataset_coll.update_one(
            {"_id": ObjectId(dataset_id)},
            {
                "$set": {
                    "status": DatasetStatus.COMPLETED,
                    "stats.processed_rows": processed_count,
                    "stats.errors": errors,
                }
            },
        )

        return {"status": "completed", "processed": processed_count}

    except Exception as e:
        logger.error(f"Dataset processing failed: {e}")
        dataset_coll.update_one(
            {"_id": ObjectId(dataset_id)},
            {"$set": {"status": DatasetStatus.FAILED, "error_details": str(e)}},
        )
        return {"status": "failed", "error": str(e)}
