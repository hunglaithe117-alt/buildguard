from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.entities.base import PyObjectId


class BuildSummary(BaseModel):
    id: str = Field(..., alias="_id")
    build_number: int
    status: str  # GitHub workflow status: "success", "failure", etc.
    extraction_status: (
        str  # Feature extraction process status: "pending", "completed", "failed"
    )
    commit_sha: str
    created_at: Optional[datetime] = None
    duration: Optional[float] = None
    num_jobs: Optional[int] = None
    num_tests: Optional[int] = None
    error_message: Optional[str] = None
    is_missing_commit: bool = False

    # Workflow info
    workflow_run_id: int

    class Config:
        populate_by_name = True


class BuildDetail(BuildSummary):
    # Git Diff features
    git_diff_src_churn: Optional[int] = None
    git_diff_test_churn: Optional[int] = None
    gh_diff_files_added: Optional[int] = None
    gh_diff_files_deleted: Optional[int] = None
    gh_diff_files_modified: Optional[int] = None
    gh_diff_tests_added: Optional[int] = None
    gh_diff_tests_deleted: Optional[int] = None

    # Repo Snapshot features
    gh_repo_age: Optional[float] = None
    gh_repo_num_commits: Optional[int] = None
    gh_sloc: Optional[int] = None

    # Logs
    error_message: Optional[str] = None

    # New Git Features
    git_prev_commit_resolution_status: Optional[str] = None
    git_prev_built_commit: Optional[str] = None
    tr_prev_build: Optional[int] = None
    gh_team_size: Optional[int] = None
    git_num_all_built_commits: Optional[int] = None
    gh_by_core_team_member: Optional[bool] = None
    gh_num_commits_on_files_touched: Optional[int] = None


class BuildListResponse(BaseModel):
    items: List[BuildSummary]
    total: int
    page: int
    size: int
