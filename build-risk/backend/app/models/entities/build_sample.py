from datetime import datetime
from typing import List, Optional

from .base import BaseEntity, PyObjectId


class BuildSample(BaseEntity):
    repo_id: PyObjectId
    workflow_run_id: int
    status: str = "pending"  # pending, completed, failed
    error_message: str | None = None
    is_missing_commit: bool = False

    # Log features
    tr_build_id: int | None = None
    tr_build_number: int | None = None
    tr_original_commit: str | None = None
    tr_jobs: List[int] = []
    tr_log_lan_all: List[str] = []
    tr_log_frameworks_all: List[str] = []
    tr_log_num_jobs: int | None = None
    tr_log_tests_run_sum: int | None = None
    tr_log_tests_failed_sum: int | None = None
    tr_log_tests_skipped_sum: int | None = None
    tr_log_tests_ok_sum: int | None = None
    tr_log_tests_fail_rate: float | None = None
    tr_log_testduration_sum: float | None = None
    tr_status: str | None = None
    tr_duration: float | None = None
    tr_log_num_jobs: int | None = None

    # Git Diff features
    git_diff_src_churn: int | None = None
    git_diff_test_churn: int | None = None
    gh_diff_files_added: int | None = None
    gh_diff_files_deleted: int | None = None
    gh_diff_files_modified: int | None = None
    gh_diff_tests_added: int | None = None
    gh_diff_tests_deleted: int | None = None
    gh_diff_src_files: int | None = None
    gh_diff_doc_files: int | None = None
    gh_diff_other_files: int | None = None

    # Repo Snapshot features
    gh_repo_age: float | None = None
    gh_repo_num_commits: int | None = None
    gh_sloc: int | None = None
    gh_test_lines_per_kloc: float | None = None
    gh_test_cases_per_kloc: float | None = None
    gh_asserts_case_per_kloc: float | None = None
    git_trigger_commit: str | None = None
    git_branch: str | None = None
    gh_lang: str | None = None
    gh_pull_req_num: Optional[int] = None
    gh_is_pr: Optional[bool] = None
    gh_pr_created_at: Optional[str] = None
    gh_project_name: Optional[str] = None
    ci_provider: str | None = None
    gh_build_started_at: datetime | None = None
    gh_description_complexity: int | None = None

    # GitHub Discussion features
    gh_num_issue_comments: int | None = None
    gh_num_commit_comments: int | None = None
    gh_num_pr_comments: int | None = None

    # Git Features
    git_prev_commit_resolution_status: str | None = None
    git_prev_built_commit: str | None = None
    tr_prev_build: int | None = None
    gh_team_size: int | None = None
    git_all_built_commits: List[str] = []
    git_num_all_built_commits: int | None = None
    gh_by_core_team_member: bool | None = None
    gh_by_core_team_member: bool | None = None
    gh_num_commits_on_files_touched: int | None = None

    # User Feedback
    feedback: dict | None = None

    # Risk Analysis
    risk_factors: List[str] = []

