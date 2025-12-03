import logging
from typing import Any, Dict, List

from bson import ObjectId
from bson.errors import InvalidId
from app.celery_app import celery_app
from app.domain.entities import BuildSample
from app.repositories import (
    BuildSampleRepository,
    ImportedRepositoryRepository,
    WorkflowRunRepository,
)
from app.services.extracts.build_log_extractor import BuildLogExtractor
from app.services.extracts.github_discussion_extractor import GitHubApiExtractor
from app.services.extracts.repo_snapshot_extractor import RepoSnapshotExtractor
from app.workers import PipelineTask
from app.utils.events import publish_build_update
from buildguard_common.tasks import (
    TASK_EXTRACT_BUILD_LOG,
    TASK_EXTRACT_GIT,
    TASK_EXTRACT_REPO_SNAPSHOT,
    TASK_EXTRACT_DISCUSSION,
    TASK_FINALIZE_SAMPLE,
)

logger = logging.getLogger(__name__)


def get_selected_features(db, build_sample: BuildSample) -> List[str] | None:
    if not build_sample.dataset_import_job_id:
        return None

    job_doc = db["dataset_import_jobs"].find_one(
        {"_id": build_sample.dataset_import_job_id}
    )
    if not job_doc:
        return None

    selected = job_doc.get("selected_features")
    if not selected:
        return None

    # Already stored as keys
    if all(isinstance(f, str) for f in selected):
        return selected

    # Convert stored ObjectIds (or strings) back to feature keys
    feature_ids: List[ObjectId] = []
    for item in selected:
        if isinstance(item, ObjectId):
            feature_ids.append(item)
        elif isinstance(item, str):
            try:
                feature_ids.append(ObjectId(item))
            except (InvalidId, TypeError):
                continue

    if not feature_ids:
        return None

    cursor = db["feature_definitions"].find(
        {"_id": {"$in": feature_ids}}, {"key": 1}
    )
    keys = [doc["key"] for doc in cursor]
    return keys or None


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name=TASK_EXTRACT_BUILD_LOG,
    queue="data_processing",
)
def extract_build_log_features(self: PipelineTask, build_id: str) -> Dict[str, Any]:
    build_sample_repo = BuildSampleRepository(self.db)
    workflow_run_repo = WorkflowRunRepository(self.db)

    build_sample = build_sample_repo.find_by_id(ObjectId(build_id))
    if not build_sample:
        logger.error(f"BuildSample {build_id} not found")
        return {}

    workflow_run = workflow_run_repo.find_by_repo_and_run_id(
        str(build_sample.repo_id), build_sample.workflow_run_id
    )
    if not workflow_run:
        logger.error(
            f"WorkflowRunRaw not found for {build_sample.repo_id} / {build_sample.workflow_run_id}"
        )
        return {}

    repo_repo = ImportedRepositoryRepository(self.db)
    repo = repo_repo.find_by_id(str(build_sample.repo_id))
    if not repo:
        logger.error(f"Repository {build_sample.repo_id} not found")
        return {}

    extractor = BuildLogExtractor()
    selected_features = get_selected_features(self.db, build_sample)
    return extractor.extract(
        build_sample, workflow_run, repo, selected_features=selected_features
    )


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name=TASK_EXTRACT_GIT,
    queue="data_processing",
)
def extract_git_features(self: PipelineTask, build_id: str) -> Dict[str, Any]:
    build_sample_repo = BuildSampleRepository(self.db)
    repo_repo = ImportedRepositoryRepository(self.db)

    build_sample = build_sample_repo.find_by_id(ObjectId(build_id))
    if not build_sample:
        logger.error(f"BuildSample {build_id} not found")
        return {}

    repo = repo_repo.find_by_id(str(build_sample.repo_id))
    if not repo:
        logger.error(f"Repository {build_sample.repo_id} not found")
        return {}

    from app.services.extracts.git_feature_extractor import GitHistoryExtractor

    extractor = GitHistoryExtractor(self.db)
    selected_features = get_selected_features(self.db, build_sample)
    features = extractor.extract(
        build_sample, None, repo, selected_features=selected_features
    )  # GitHistoryExtractor currently does not require workflow_run.

    # Save features immediately so they are available for subsequent tasks in the chain
    if features:
        # Remove warning before saving to DB
        features_to_save = features.copy()
        features_to_save.pop("extraction_warning", None)
        if features_to_save:
            build_sample_repo.update_one(build_id, features_to_save)

    return features


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name=TASK_EXTRACT_REPO_SNAPSHOT,
    queue="data_processing",
)
def extract_repo_snapshot_features(self: PipelineTask, build_id: str) -> Dict[str, Any]:
    build_sample_repo = BuildSampleRepository(self.db)
    workflow_run_repo = WorkflowRunRepository(self.db)
    repo_repo = ImportedRepositoryRepository(self.db)

    build_sample = build_sample_repo.find_by_id(ObjectId(build_id))
    if not build_sample:
        logger.error(f"BuildSample {build_id} not found")
        return {}

    workflow_run = workflow_run_repo.find_by_repo_and_run_id(
        str(build_sample.repo_id), build_sample.workflow_run_id
    )
    if not workflow_run:
        logger.error(
            f"WorkflowRunRaw not found for {build_sample.repo_id} / {build_sample.workflow_run_id}"
        )
        return {}

    repo = repo_repo.find_by_id(str(build_sample.repo_id))
    if not repo:
        logger.error(f"Repository {build_sample.repo_id} not found")
        return {}

    extractor = RepoSnapshotExtractor(self.db)
    selected_features = get_selected_features(self.db, build_sample)
    return extractor.extract(
        build_sample, workflow_run, repo, selected_features=selected_features
    )


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name=TASK_EXTRACT_DISCUSSION,
    queue="data_processing",
)
def extract_github_discussion_features(
    self: PipelineTask, build_id: str
) -> Dict[str, Any]:
    build_sample_repo = BuildSampleRepository(self.db)
    workflow_run_repo = WorkflowRunRepository(self.db)
    repo_repo = ImportedRepositoryRepository(self.db)

    build_sample = build_sample_repo.find_by_id(ObjectId(build_id))
    if not build_sample:
        logger.error(f"BuildSample {build_id} not found")
        return {}

    workflow_run = workflow_run_repo.find_by_repo_and_run_id(
        str(build_sample.repo_id), build_sample.workflow_run_id
    )
    if not workflow_run:
        logger.error(
            f"WorkflowRunRaw not found for {build_sample.repo_id} / {build_sample.workflow_run_id}"
        )
        return {}

    repo = repo_repo.find_by_id(str(build_sample.repo_id))
    if not repo:
        logger.error(f"Repository {build_sample.repo_id} not found")
        return {}

    extractor = GitHubApiExtractor(self.db)
    selected_features = get_selected_features(self.db, build_sample)
    return extractor.extract(
        build_sample, workflow_run, repo, selected_features=selected_features
    )


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name=TASK_FINALIZE_SAMPLE,
    queue="data_processing",
)
def finalize_build_sample(
    self: PipelineTask, results: List[Dict[str, Any]], build_id: str
) -> Dict[str, Any]:
    build_sample_repo = BuildSampleRepository(self.db)
    merged_updates = {}
    errors = []

    warnings = []
    for result in results:
        if isinstance(result, dict):
            if "error" in result:
                errors.append(result["error"])
            if "extraction_warning" in result:
                warnings.append(result["extraction_warning"])

            # Merge updates (excluding special keys)
            clean_result = {
                k: v
                for k, v in result.items()
                if k not in ["error", "extraction_warning"]
            }
            merged_updates.update(clean_result)

        elif isinstance(result, Exception):
            errors.append(str(result))

    if errors:
        status = "failed"
        error_message = "; ".join(errors)
        merged_updates["status"] = status
        merged_updates["error_message"] = error_message
    else:
        status = "completed"
        merged_updates["status"] = status
        if warnings:
            merged_updates["error_message"] = "Warning: " + "; ".join(warnings)
            if any("Commit not found (orphan/fork)" in w for w in warnings):
                merged_updates["is_missing_commit"] = True

    build_sample_repo.update_one(build_id, merged_updates)

    build = build_sample_repo.find_by_id(ObjectId(build_id))
    if build:
        publish_build_update(str(build.repo_id), build_id, merged_updates["status"])

    return {"status": merged_updates["status"], "build_id": build_id}
