from datetime import datetime, timezone
from typing import List, Optional
from app.domain.entities import BuildSample
from app.repositories import BuildSampleRepository, ImportedRepositoryRepository
from pymongo.database import Database
import logging
from buildguard_common.repositories.base import CollectionName

logger = logging.getLogger(__name__)


class HeuristicEngine:
    def __init__(self, db: Database):
        self.db = db
        self.workflow_run_repo = WorkflowRunRepository(db)

    def apply_all(self, build: BuildSample) -> List[str]:
        factors = []
        try:
            if self.check_high_churn(build):
                factors.append("High Churn")
            if self.check_late_night(build):
                factors.append("Late Night")
            if self.check_junior_commit(build):
                factors.append("Junior Commit")
        except Exception as e:
            logger.error(f"Error applying heuristics for build {build.id}: {e}")
        return factors

    def check_high_churn(self, build: BuildSample) -> bool:
        # Threshold: > 50 files modified
        # We check gh_diff_files_modified (GitHub API) or git_diff_src_churn (Git)
        # Roadmap said "> 50 files".
        if build.gh_diff_files_modified and build.gh_diff_files_modified > 50:
            return True
        return False

    def check_late_night(self, build: BuildSample) -> bool:
        # Threshold: 00:00 - 06:00
        # Use gh_build_started_at (datetime)
        if not build.gh_build_started_at:
            return False

        # Ensure UTC
        dt = build.gh_build_started_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # We use UTC for now as we don't have user timezone.
        # 00:00 - 06:00 UTC
        hour = dt.hour
        return 0 <= hour < 6

    def check_junior_commit(self, build: BuildSample) -> bool:
        # Threshold: First commit < 90 days ago
        if not build.workflow_run_id:
            return False

        # Get current workflow run to find actor
        current_run = self.workflow_run_repo.find_by_repo_and_run_id(
            str(build.repo_id), build.workflow_run_id
        )
        if not current_run or not current_run.raw_payload:
            return False

        actor = current_run.raw_payload.get("triggering_actor", {})
        login = actor.get("login")
        if not login:
            return False

        # Find first run by this actor in this repo
        # We can query workflow_runs collection
        # We need to ensure we have history. If we just imported, we might not have full history.
        # But assuming we have imported history.

        first_run = self.db[CollectionName.WORKFLOW_RUNS.value].find_one(
            {"repo_id": build.repo_id, "raw_payload.triggering_actor.login": login},
            sort=[("created_at", 1)],
        )

        if not first_run:
            return False  # Should not happen as current run exists

        first_date = first_run["created_at"]
        if isinstance(first_date, str):
            first_date = datetime.fromisoformat(first_date.replace("Z", "+00:00"))
        if first_date.tzinfo is None:
            first_date = first_date.replace(tzinfo=timezone.utc)

        current_date = current_run.created_at
        if current_date.tzinfo is None:
            current_date = current_date.replace(tzinfo=timezone.utc)

        delta = current_date - first_date
        return delta.days < 90
