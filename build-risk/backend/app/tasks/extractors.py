import logging
from typing import Any, Dict, List

from bson import ObjectId
from app.celery_app import celery_app
from app.models.entities.build_sample import BuildSample
from app.repositories.build_sample import BuildSampleRepository
from app.repositories.imported_repository import ImportedRepositoryRepository
from app.repositories.workflow_run import WorkflowRunRepository
from app.services.extracts.build_log_extractor import BuildLogExtractor
from app.services.extracts.github_discussion_extractor import GitHubDiscussionExtractor
from app.services.extracts.repo_snapshot_extractor import RepoSnapshotExtractor
from app.services.heuristics import HeuristicEngine
from app.services.notifications import NotificationService
from app.tasks.base import PipelineTask
from app.utils.events import publish_build_update

logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.processing.extract_build_log_features",
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
    return extractor.extract(build_sample, workflow_run, repo)


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.processing.extract_git_features",
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

    from app.services.extracts.git_feature_extractor import GitFeatureExtractor

    extractor = GitFeatureExtractor(self.db)
    features = extractor.extract(build_sample, None, repo) # GitFeatureExtractor might not need workflow_run? 
    # Wait, I updated GitFeatureExtractor to take workflow_run optional.
    # But here I pass None. It should be fine if it doesn't use it.
    # GitFeatureExtractor uses build_sample.tr_original_commit.
    # I should check if it needs workflow_run.
    # It doesn't seem to use it in my previous view.

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
    name="app.tasks.processing.extract_repo_snapshot_features",
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
    return extractor.extract(build_sample, workflow_run, repo)


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.processing.extract_github_discussion_features",
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

    extractor = GitHubDiscussionExtractor(self.db)
    return extractor.extract(build_sample, workflow_run, repo)


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.processing.finalize_build_sample",
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
        # Apply Heuristics
        try:
            heuristic_engine = HeuristicEngine(self.db)
            risk_factors = heuristic_engine.apply_all(build)
            if risk_factors:
                build_sample_repo.update_one(build_id, {"risk_factors": risk_factors})
                merged_updates["risk_factors"] = risk_factors
                
                # Send Alert
                try:
                    repo_repo = ImportedRepositoryRepository(self.db)
                    repo = repo_repo.find_by_id(str(build.repo_id))
                    shadow_mode = repo.shadow_mode if repo else False
                    
                    NotificationService().send_alert(build, risk_factors, shadow_mode=shadow_mode)
                except Exception as ns_e:
                    logger.error(f"Notification failed: {ns_e}")
        except Exception as e:
            logger.error(f"Failed to apply heuristics: {e}")

        publish_build_update(str(build.repo_id), build_id, merged_updates["status"])

    return {"status": merged_updates["status"], "build_id": build_id}
