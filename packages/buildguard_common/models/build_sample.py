from datetime import datetime
from typing import List, Optional

from .base import BaseEntity, PyObjectId


class BuildSample(BaseEntity):
    repo_id: PyObjectId
    workflow_run_id: int
    status: str = "pending"  # pending, completed, failed
    error_message: Optional[str] = None
    is_missing_commit: bool = False
    dataset_import_job_id: Optional[PyObjectId] = None

    # Log features
    tr_build_id: Optional[int] = None
    tr_build_number: Optional[int] = None
    tr_original_commit: Optional[str] = None
    tr_jobs: List[int] = []
    tr_log_lan_all: List[str] = []
    tr_log_frameworks_all: List[str] = []
    tr_log_num_jobs: Optional[int] = None
    tr_log_tests_run_sum: Optional[int] = None
    tr_log_tests_failed_sum: Optional[int] = None
    tr_log_tests_skipped_sum: Optional[int] = None
    tr_log_tests_ok_sum: Optional[int] = None
    tr_log_tests_fail_rate: Optional[float] = None
    tr_log_testduration_sum: Optional[float] = None
    tr_status: Optional[str] = None
    tr_duration: Optional[float] = None
    tr_log_num_jobs: Optional[int] = None

    # Git Diff features
    git_diff_src_churn: Optional[int] = None
    git_diff_test_churn: Optional[int] = None
    gh_diff_files_added: Optional[int] = None
    gh_diff_files_deleted: Optional[int] = None
    gh_diff_files_modified: Optional[int] = None
    gh_diff_tests_added: Optional[int] = None
    gh_diff_tests_deleted: Optional[int] = None
    gh_diff_src_files: Optional[int] = None
    gh_diff_doc_files: Optional[int] = None
    gh_diff_other_files: Optional[int] = None

    # Repo Snapshot features
    gh_repo_age: Optional[float] = None
    gh_repo_num_commits: Optional[int] = None
    gh_sloc: Optional[int] = None
    gh_test_lines_per_kloc: Optional[float] = None
    gh_test_cases_per_kloc: Optional[float] = None
    gh_asserts_case_per_kloc: Optional[float] = None
    git_trigger_commit: Optional[str] = None
    git_branch: Optional[str] = None
    gh_lang: Optional[str] = None
    gh_pull_req_num: Optional[int] = None
    gh_is_pr: Optional[bool] = None
    gh_pr_created_at: Optional[str] = None
    gh_project_name: Optional[str] = None
    ci_provider: Optional[str] = None
    gh_build_started_at: Optional[datetime] = None
    gh_description_complexity: Optional[int] = None

    # GitHub Discussion features
    gh_num_issue_comments: Optional[int] = None
    gh_num_commit_comments: Optional[int] = None
    gh_num_pr_comments: Optional[int] = None

    # Git Features
    git_prev_commit_resolution_status: Optional[str] = None
    git_prev_built_commit: Optional[str] = None
    tr_prev_build: Optional[int] = None
    gh_team_size: Optional[int] = None
    git_all_built_commits: List[str] = []
    git_num_all_built_commits: Optional[int] = None
    gh_by_core_team_member: Optional[bool] = None
    gh_num_commits_on_files_touched: Optional[int] = None

    # User Feedback
    feedback: Optional[dict] = None
