import logging
from typing import Any, Dict

from app.services.sonar_service import SonarService
from app.repositories import (
    BuildSampleRepository,
    ImportedRepositoryRepository,
    WorkflowRunRepository,
)
from app.domain.entities import BuildSample
from pymongo.database import Database

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self, db: Database):
        self.db = db
        self.sonar_service = SonarService(db)
        self.build_sample_repo = BuildSampleRepository(db)
        self.repo_repo = ImportedRepositoryRepository(db)
        self.workflow_run_repo = WorkflowRunRepository(db)

    def run(
        self,
        repo_id: str,
        commit_sha: str,
        build_id: str | None = None,
        workflow_run: Any | None = None,
    ):
        logger.info(f"🚀 Starting pipeline for {repo_id}@{commit_sha}")

        try:
            if build_id:
                build_sample = self.build_sample_repo.find_by_id(build_id)
                if not build_sample:
                    logger.error(f"BuildSample {build_id} not found")
                    return
            else:
                logger.warning(
                    "No build_id provided, skipping BuildSample update for now"
                )
                # Create a temporary build sample for context if needed, or fail?
                # The registry needs a BuildSample in context.
                # If we don't have one, we can't proceed with new system easily.
                # But legacy code handled build_sample=None in some cases?
                # Actually legacy code checked `if build_sample:` before extracting.
                # So if no build_sample, no extraction happened.
                return

            repo = self.repo_repo.find_by_id(repo_id)
            if not repo:
                logger.error(f"Repository {repo_id} not found")
                return

            if not workflow_run and build_sample and build_sample.workflow_run_id:
                workflow_run = self.workflow_run_repo.find_by_repo_and_run_id(
                    repo_id, build_sample.workflow_run_id
                )

            # Initialize Context
            from app.services.features.base import ExtractionContext, FeatureSource
            from app.services.features.registry import registry

            context = ExtractionContext(
                build_sample=build_sample,
                workflow_run=workflow_run,
                repo=repo,
                db=self.db,
            )

            # Determine selected features if this build is part of a dataset import job
            selected_features = self._get_selected_features(build_sample)

            updates: Dict[str, Any] = {}

            # 1) Build log features
            if workflow_run:
                logger.info("Extracting build log features...")
                log_features = registry.extract_source(
                    FeatureSource.BUILD_LOG, context, updates, selected_features
                )
                updates.update(log_features)
                # We don't strictly need to update build_sample object incrementally
                # if we pass 'updates' dict as known_values.
                # But for safety/consistency with legacy:
                build_sample = self._apply_updates(build_sample, log_features)

            # 2) Git features (commit lists, churn metrics)
            logger.info("Extracting Git features...")
            git_features = registry.extract_source(
                FeatureSource.GIT_HISTORY, context, updates, selected_features
            )
            updates.update(git_features)
            build_sample = self._apply_updates(build_sample, git_features)

            # 3) Repo snapshot features (PR/context metadata)
            if workflow_run:
                logger.info("Extracting repository snapshot features...")
                snapshot_features = registry.extract_source(
                    FeatureSource.REPO_SNAPSHOT, context, updates, selected_features
                )
                updates.update(snapshot_features)
                build_sample = self._apply_updates(build_sample, snapshot_features)

            # 4) GitHub discussion features (needs commit/PR info)
            if workflow_run:
                logger.info("Extracting GitHub discussion features...")
                discussion_features = registry.extract_source(
                    FeatureSource.GITHUB_API, context, updates, selected_features
                )
                updates.update(discussion_features)
                build_sample = self._apply_updates(build_sample, discussion_features)

            if updates and build_id:
                updates.pop("extraction_warning", None)
                self.build_sample_repo.update_one(build_id, updates)

            # 5) Risk label from log failure rate (not Sonar metrics)
            risk_label = self._calculate_risk_label(build_sample, updates)
            logger.info(f"Calculated Risk Label: {risk_label}")

            # 6) Optional Sonar scan
            sonar_ran = False
            if getattr(repo, "auto_sonar_scan", False):
                logger.info("Triggering SonarQube scan...")
                try:
                    self.sonar_service.scan_and_wait(repo_id, commit_sha)
                    sonar_ran = True
                except Exception as e:
                    logger.error("Sonar scan failed: %s", e)

            if build_id:
                status = "completed"
                if not sonar_ran and getattr(repo, "auto_sonar_scan", False):
                    status = "awaiting_scan"
                self.build_sample_repo.update_one(
                    build_id,
                    {
                        "risk_label": risk_label,
                        "pipeline_status": status,
                    },
                )

            logger.info("✅ Pipeline finished successfully")

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {str(e)}")
            if build_id:
                self.build_sample_repo.update_one(
                    build_id, {"pipeline_status": "failed", "error_message": str(e)}
                )
            raise

    def _get_selected_features(self, build_sample: BuildSample) -> List[str] | None:
        if not build_sample.dataset_import_job_id:
            return None

        job_doc = self.db["dataset_import_jobs"].find_one(
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

        from bson import ObjectId
        from bson.errors import InvalidId

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

        cursor = self.db["feature_definitions"].find(
            {"_id": {"$in": feature_ids}}, {"key": 1}
        )
        keys = [doc["key"] for doc in cursor]
        return keys or None

    def _apply_updates(
        self, sample: BuildSample, updates: Dict[str, Any]
    ) -> BuildSample:
        for key, value in updates.items():
            try:
                setattr(sample, key, value)
            except Exception:
                continue
        return sample

    def _calculate_risk_label(
        self, sample: BuildSample | None, updates: Dict[str, Any]
    ) -> str:
        fail_rate = updates.get("tr_log_tests_fail_rate") if updates else None
        if fail_rate is None and sample:
            fail_rate = getattr(sample, "tr_log_tests_fail_rate", None)

        if fail_rate is None:
            return "UNKNOWN"
        try:
            rate = float(fail_rate)
        except (TypeError, ValueError):
            return "UNKNOWN"

        if rate >= 0.5:
            return "HIGH"
        if rate >= 0.2:
            return "MEDIUM"
        return "LOW"
