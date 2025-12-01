import logging
from typing import Any, Dict

from app.services.extracts.git_feature_extractor import GitFeatureExtractor
from app.services.sonar_service import SonarService
from app.infra.repositories import BuildSampleRepository, ImportedRepositoryRepository
from app.domain.entities import BuildSample
from pymongo.database import Database

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self, db: Database):
        self.db = db
        self.git_extractor = GitFeatureExtractor(db)
        self.sonar_service = SonarService(db)
        self.build_sample_repo = BuildSampleRepository(db)
        self.repo_repo = ImportedRepositoryRepository(db)

    def run(self, repo_id: str, commit_sha: str, build_id: str = None):
        logger.info(f"🚀 Starting pipeline for {repo_id}@{commit_sha}")

        try:
            # 1. Get BuildSample (if exists, or create/update?)
            # Usually build_id is passed.
            if build_id:
                build_sample = self.build_sample_repo.find_by_id(build_id)
                if not build_sample:
                    logger.error(f"BuildSample {build_id} not found")
                    return
            else:
                # Find by commit?
                logger.warning(
                    "No build_id provided, skipping BuildSample update for now"
                )
                build_sample = None

            repo = self.repo_repo.find_by_id(repo_id)
            if not repo:
                logger.error(f"Repository {repo_id} not found")
                return

            # 2. Extract Git Features
            logger.info("Extracting Git features...")
            # GitFeatureExtractor.extract(build_sample, workflow_run, repo)
            # It expects build_sample.
            git_features = {}
            if build_sample:
                git_features = self.git_extractor.extract(build_sample, None, repo)
                if git_features:
                    # Remove warning before saving
                    features_to_save = git_features.copy()
                    features_to_save.pop("extraction_warning", None)
                    self.build_sample_repo.update_one(build_id, features_to_save)

            # 3. Trigger Sonar Scan
            logger.info("Triggering SonarQube scan...")
            sonar_metrics = self.sonar_service.scan_and_wait(repo_id, commit_sha)

            # 4. Calculate Risk Label
            risk_label = self._calculate_risk_label(sonar_metrics)
            logger.info(f"Calculated Risk Label: {risk_label}")

            # 5. Update DB
            if build_id:
                self.build_sample_repo.update_one(
                    build_id, {"risk_label": risk_label, "pipeline_status": "completed"}
                )

            logger.info("✅ Pipeline finished successfully")

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {str(e)}")
            if build_id:
                self.build_sample_repo.update_one(
                    build_id, {"pipeline_status": "failed", "error_message": str(e)}
                )
            raise

    def _calculate_risk_label(self, sonar_metrics: Dict[str, Any]) -> str:
        score = 0
        # Parse metrics which are strings in Sonar response usually
        bugs = int(sonar_metrics.get("bugs", 0))
        vulnerabilities = int(sonar_metrics.get("vulnerabilities", 0))

        score += bugs * 10
        score += vulnerabilities * 20

        if score > 50:
            return "HIGH"
        if score > 20:
            return "MEDIUM"
        return "LOW"
