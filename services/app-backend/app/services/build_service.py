from typing import List, Optional

from bson import ObjectId
from pymongo.database import Database

from app.dtos.build import BuildDetail, BuildListResponse, BuildSummary
from buildguard_common.models import BuildSample, WorkflowRunRaw
from app.celery_app import celery_app
from datetime import datetime, timezone
from buildguard_common.repositories.base import CollectionName


class BuildService:
    def __init__(self, db: Database):
        self.db = db
        self.build_collection = db[CollectionName.BUILD_SAMPLES.value]
        self.workflow_collection = db[CollectionName.WORKFLOW_RUNS.value]

    def get_builds_by_repo(
        self, repo_id: str, skip: int = 0, limit: int = 20, q: Optional[str] = None
    ) -> BuildListResponse:
        query = {"repo_id": ObjectId(repo_id)}

        if q:
            # Try to match build number (int) or commit SHA/status (str)
            or_conditions = []
            if q.isdigit():
                or_conditions.append({"tr_build_number": int(q)})

            or_conditions.append({"tr_original_commit": {"$regex": q, "$options": "i"}})
            or_conditions.append({"status": {"$regex": q, "$options": "i"}})

            query["$or"] = or_conditions

        total = self.build_collection.count_documents(query)
        cursor = (
            self.build_collection.find(query)
            .sort("tr_build_number", -1)
            .skip(skip)
            .limit(limit)
        )

        build_samples = [BuildSample(**doc) for doc in cursor]

        if not build_samples:
            return BuildListResponse(
                items=[], total=total, page=skip // limit + 1, size=limit
            )

        # Fetch workflow runs
        workflow_run_ids = [b.workflow_run_id for b in build_samples]
        workflow_runs_cursor = self.workflow_collection.find(
            {"workflow_run_id": {"$in": workflow_run_ids}}
        )
        workflow_runs = {
            w["workflow_run_id"]: WorkflowRunRaw(**w) for w in workflow_runs_cursor
        }

        # Fetch scan jobs
        commit_shas = [
            b.tr_original_commit for b in build_samples if b.tr_original_commit
        ]
        scan_jobs_cursor = self.db[CollectionName.SCAN_JOBS.value].find(
            {"project_id": repo_id, "commit_sha": {"$in": commit_shas}}
        )
        scan_jobs = {job["commit_sha"]: job for job in scan_jobs_cursor}

        items = []
        for sample in build_samples:
            workflow = workflow_runs.get(sample.workflow_run_id)
            commit_sha = sample.tr_original_commit or (
                workflow.head_sha if workflow else ""
            )
            scan_job = scan_jobs.get(commit_sha)

            items.append(
                BuildSummary(
                    _id=str(sample.id),
                    build_number=sample.tr_build_number or 0,
                    status=sample.tr_status or "unknown",
                    extraction_status=sample.status,
                    commit_sha=commit_sha,
                    created_at=workflow.created_at if workflow else None,
                    duration=sample.tr_duration,
                    num_jobs=sample.tr_log_num_jobs,
                    num_tests=sample.tr_log_tests_run_sum,
                    workflow_run_id=sample.workflow_run_id,
                    sonar_scan_status=scan_job["status"] if scan_job else None,
                )
            )

        return BuildListResponse(
            items=items,
            total=total,
            page=skip // limit + 1,
            size=limit,
        )

    def get_build_detail(self, build_id: str) -> Optional[BuildDetail]:
        doc = self.build_collection.find_one({"_id": ObjectId(build_id)})
        if not doc:
            return None

        sample = BuildSample(**doc)
        workflow_doc = self.workflow_collection.find_one(
            {"workflow_run_id": sample.workflow_run_id}
        )
        workflow = WorkflowRunRaw(**workflow_doc) if workflow_doc else None

        return BuildDetail(
            _id=str(sample.id),
            build_number=sample.tr_build_number or 0,
            status=sample.tr_status or "unknown",
            extraction_status=sample.status,
            commit_sha=sample.tr_original_commit
            or (workflow.head_sha if workflow else ""),
            created_at=workflow.created_at if workflow else None,
            duration=sample.tr_duration,
            num_jobs=sample.tr_log_num_jobs,
            num_tests=sample.tr_log_tests_run_sum,
            workflow_run_id=sample.workflow_run_id,
            # Details
            git_diff_src_churn=sample.git_diff_src_churn,
            git_diff_test_churn=sample.git_diff_test_churn,
            gh_diff_files_added=sample.gh_diff_files_added,
            gh_diff_files_deleted=sample.gh_diff_files_deleted,
            gh_diff_files_modified=sample.gh_diff_files_modified,
            gh_diff_tests_added=sample.gh_diff_tests_added,
            gh_diff_tests_deleted=sample.gh_diff_tests_deleted,
            gh_repo_age=sample.gh_repo_age,
            gh_repo_num_commits=sample.gh_repo_num_commits,
            gh_sloc=sample.gh_sloc,
            error_message=sample.error_message,
            # New Git Features
            git_prev_commit_resolution_status=sample.git_prev_commit_resolution_status,
            git_prev_built_commit=sample.git_prev_built_commit,
            tr_prev_build=sample.tr_prev_build,
            gh_team_size=sample.gh_team_size,
            git_num_all_built_commits=sample.git_num_all_built_commits,
            gh_by_core_team_member=sample.gh_by_core_team_member,
            gh_num_commits_on_files_touched=sample.gh_num_commits_on_files_touched,
        )

    def get_recent_builds(self, limit: int = 10) -> List[BuildSummary]:
        cursor = self.build_collection.find({}).sort("_id", -1).limit(limit)

        build_samples = [BuildSample(**doc) for doc in cursor]
        if not build_samples:
            return []

        # Fetch workflow runs
        workflow_run_ids = [b.workflow_run_id for b in build_samples]
        workflow_runs_cursor = self.workflow_collection.find(
            {"workflow_run_id": {"$in": workflow_run_ids}}
        )
        workflow_runs = {
            w["workflow_run_id"]: WorkflowRunRaw(**w) for w in workflow_runs_cursor
        }

        items = []
        for sample in build_samples:
            workflow = workflow_runs.get(sample.workflow_run_id)

            items.append(
                BuildSummary(
                    _id=str(sample.id),
                    build_number=sample.tr_build_number or 0,
                    status=sample.tr_status or "unknown",
                    extraction_status=sample.status,
                    commit_sha=sample.tr_original_commit
                    or (workflow.head_sha if workflow else ""),
                    created_at=workflow.created_at if workflow else None,
                    duration=sample.tr_duration,
                    num_jobs=sample.tr_log_num_jobs,
                    num_tests=sample.tr_log_tests_run_sum,
                    workflow_run_id=sample.workflow_run_id,
                )
            )
        return items

    def trigger_sonar_scan_direct(self, build_id: str):
        from app.services.sonar_service import SonarService

        # Verify build exists
        if not self.build_collection.find_one({"_id": ObjectId(build_id)}):
            raise ValueError("Build not found")

        # Trigger Scan via SonarService
        service = SonarService(self.db)
        service.trigger_scan(build_id)
        return True

    def trigger_rescan(self, build_id: str, user_id: str):
        doc = self.build_collection.find_one({"_id": ObjectId(build_id)})
        if not doc:
            raise ValueError("Build not found")

        repo_id = str(doc["repo_id"])
        run_id = doc["workflow_run_id"]

        # Trigger processing task
        celery_app.send_task(
            "app.tasks.processing.process_workflow_run", args=[repo_id, run_id]
        )
        return True

    def submit_feedback(
        self, build_id: str, user_id: str, is_false_positive: bool, reason: str
    ):
        doc = self.build_collection.find_one({"_id": ObjectId(build_id)})
        if not doc:
            raise ValueError("Build not found")

        feedback = {
            "user_id": user_id,
            "is_false_positive": is_false_positive,
            "reason": reason,
            "created_at": datetime.now(timezone.utc),
        }

        self.build_collection.update_one(
            {"_id": ObjectId(build_id)}, {"$set": {"feedback": feedback}}
        )
        return feedback
