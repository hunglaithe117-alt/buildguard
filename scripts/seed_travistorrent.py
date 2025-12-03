import logging
import os
from enum import Enum
from typing import List, Dict, Optional, Any
from pymongo import MongoClient
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("MONGO_DATABASE", "buildguard")

# --- Local Model Definitions to avoid Import Errors ---


class FeatureDataType(str, Enum):
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"
    CATEGORY = "category"


class FeatureSourceType(str, Enum):
    METADATA = "metadata"
    CSV_MAPPED = "csv_mapped"
    GIT_EXTRACT = "git_extract"
    BUILD_LOG_EXTRACT = "build_log_extract"
    REPO_SNAPSHOT_EXTRACT = "repo_snapshot_extract"
    DERIVED = "derived"


class FeatureDefinition(BaseModel):
    key: str
    name: str
    description: Optional[str] = None
    data_type: FeatureDataType
    default_source: FeatureSourceType
    extraction_config: Optional[dict] = None
    is_active: bool = True


class DatasetTemplate(BaseModel):
    name: str
    description: Optional[str] = None
    feature_keys: List[str] = []
    default_mapping: Dict[str, str] = {}


def seed_travistorrent():
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]

    features_collection = db["feature_definitions"]
    templates_collection = db["dataset_templates"]

    # 1. Define Features
    features = [
        # --- Metadata ---
        FeatureDefinition(
            key="tr_build_id",
            name="Travis Build ID",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.CSV_MAPPED,
            description="Unique identifier for the build in Travis CI",
        ),
        FeatureDefinition(
            key="gh_project_name",
            name="Project Name",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.CSV_MAPPED,
            description="GitHub repository name (owner/repo)",
        ),
        FeatureDefinition(
            key="git_trigger_commit",
            name="Trigger Commit",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.CSV_MAPPED,
            description="Commit hash that triggered the build",
        ),
        FeatureDefinition(
            key="git_branch",
            name="Git Branch",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.CSV_MAPPED,
            description="Branch name",
        ),
        FeatureDefinition(
            key="gh_lang",
            name="Language",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.CSV_MAPPED,
            description="Main language of the repository",
        ),
        FeatureDefinition(
            key="ci_provider",
            name="CI Provider",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.CSV_MAPPED,
            description="CI Provider (e.g., Travis, GitHub Actions)",
        ),
        FeatureDefinition(
            key="gh_build_started_at",
            name="Build Started At",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.CSV_MAPPED,
            description="Timestamp when build started",
        ),
        FeatureDefinition(
            key="gh_is_pr",
            name="Is PR",
            data_type=FeatureDataType.BOOLEAN,
            default_source=FeatureSourceType.CSV_MAPPED,
            description="Whether the build was triggered by a PR",
        ),
        FeatureDefinition(
            key="gh_pr_created_at",
            name="PR Created At",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.CSV_MAPPED,
            description="Timestamp when PR was created",
        ),
        FeatureDefinition(
            key="gh_pull_req_num",
            name="PR Number",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.CSV_MAPPED,
            description="Pull Request Number",
        ),
        # --- Build Log Features ---
        FeatureDefinition(
            key="tr_log_num_jobs",
            name="Number of Jobs",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.BUILD_LOG_EXTRACT,
            extraction_config={"key": "tr_log_num_jobs"},
            description="Number of jobs in the build",
        ),
        FeatureDefinition(
            key="tr_log_tests_run_sum",
            name="Tests Run",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.BUILD_LOG_EXTRACT,
            extraction_config={"key": "tr_log_tests_run_sum"},
            description="Total number of tests run",
        ),
        FeatureDefinition(
            key="tr_log_tests_failed_sum",
            name="Tests Failed",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.BUILD_LOG_EXTRACT,
            extraction_config={"key": "tr_log_tests_failed_sum"},
            description="Total number of tests failed",
        ),
        FeatureDefinition(
            key="tr_log_tests_skipped_sum",
            name="Tests Skipped",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.BUILD_LOG_EXTRACT,
            extraction_config={"key": "tr_log_tests_skipped_sum"},
            description="Total number of tests skipped",
        ),
        FeatureDefinition(
            key="tr_log_tests_ok_sum",
            name="Tests Passed",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.BUILD_LOG_EXTRACT,
            extraction_config={"key": "tr_log_tests_ok_sum"},
            description="Total number of tests passed",
        ),
        FeatureDefinition(
            key="tr_log_tests_fail_rate",
            name="Test Fail Rate",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.BUILD_LOG_EXTRACT,
            extraction_config={"key": "tr_log_tests_fail_rate"},
            description="Ratio of failed tests to total tests",
        ),
        FeatureDefinition(
            key="tr_log_testduration_sum",
            name="Test Duration",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.BUILD_LOG_EXTRACT,
            extraction_config={"key": "tr_log_testduration_sum"},
            description="Total duration of tests in seconds",
        ),
        FeatureDefinition(
            key="tr_status",
            name="Build Status",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.BUILD_LOG_EXTRACT,
            extraction_config={"key": "tr_status"},
            description="Status of the build (passed, failed, etc.)",
        ),
        FeatureDefinition(
            key="tr_duration",
            name="Build Duration",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.BUILD_LOG_EXTRACT,
            extraction_config={"key": "tr_duration"},
            description="Total duration of the build in seconds",
        ),
        FeatureDefinition(
            key="tr_jobs",
            name="Job IDs",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.BUILD_LOG_EXTRACT,
            extraction_config={"key": "tr_jobs"},
            description="List of Job IDs",
        ),
        FeatureDefinition(
            key="tr_log_lan_all",
            name="Languages (Log)",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.BUILD_LOG_EXTRACT,
            extraction_config={"key": "tr_log_lan_all"},
            description="Languages detected in logs/repo",
        ),
        FeatureDefinition(
            key="tr_log_frameworks_all",
            name="Frameworks (Log)",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.BUILD_LOG_EXTRACT,
            extraction_config={"key": "tr_log_frameworks_all"},
            description="Test frameworks detected in logs",
        ),
        # --- Git Diff Features ---
        FeatureDefinition(
            key="git_diff_src_churn",
            name="Source Churn",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "git_diff_src_churn"},
            description="Churn in source code files",
        ),
        FeatureDefinition(
            key="git_diff_test_churn",
            name="Test Churn",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "git_diff_test_churn"},
            description="Churn in test code files",
        ),
        FeatureDefinition(
            key="gh_diff_files_added",
            name="Files Added",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "gh_diff_files_added"},
            description="Number of files added in the commit",
        ),
        FeatureDefinition(
            key="gh_diff_files_deleted",
            name="Files Deleted",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "gh_diff_files_deleted"},
            description="Number of files deleted in the commit",
        ),
        FeatureDefinition(
            key="gh_diff_files_modified",
            name="Files Modified",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "gh_diff_files_modified"},
            description="Number of files modified in the commit",
        ),
        FeatureDefinition(
            key="gh_diff_tests_added",
            name="Tests Added",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "gh_diff_tests_added"},
            description="Number of test cases added",
        ),
        FeatureDefinition(
            key="gh_diff_tests_deleted",
            name="Tests Deleted",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "gh_diff_tests_deleted"},
            description="Number of test cases deleted",
        ),
        FeatureDefinition(
            key="gh_diff_src_files",
            name="Source Files Touched",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "gh_diff_src_files"},
            description="Number of source files touched",
        ),
        FeatureDefinition(
            key="gh_diff_doc_files",
            name="Doc Files Touched",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "gh_diff_doc_files"},
            description="Number of documentation files touched",
        ),
        FeatureDefinition(
            key="gh_diff_other_files",
            name="Other Files Touched",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "gh_diff_other_files"},
            description="Number of other files touched",
        ),
        # --- Repo Snapshot Features ---
        FeatureDefinition(
            key="gh_repo_age",
            name="Repo Age",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.REPO_SNAPSHOT_EXTRACT,
            extraction_config={"key": "gh_repo_age"},
            description="Age of the repository in days",
        ),
        FeatureDefinition(
            key="gh_repo_num_commits",
            name="Num Commits",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.REPO_SNAPSHOT_EXTRACT,
            extraction_config={"key": "gh_repo_num_commits"},
            description="Total number of commits in the repository",
        ),
        FeatureDefinition(
            key="gh_sloc",
            name="SLOC",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.REPO_SNAPSHOT_EXTRACT,
            extraction_config={"key": "gh_sloc"},
            description="Source Lines of Code",
        ),
        FeatureDefinition(
            key="gh_test_lines_per_kloc",
            name="Test Lines/KLOC",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.REPO_SNAPSHOT_EXTRACT,
            extraction_config={"key": "gh_test_lines_per_kloc"},
            description="Test lines per 1000 lines of code",
        ),
        FeatureDefinition(
            key="gh_test_cases_per_kloc",
            name="Test Cases/KLOC",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.REPO_SNAPSHOT_EXTRACT,
            extraction_config={"key": "gh_test_cases_per_kloc"},
            description="Test cases per 1000 lines of code",
        ),
        FeatureDefinition(
            key="gh_asserts_case_per_kloc",
            name="Asserts/KLOC",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.REPO_SNAPSHOT_EXTRACT,
            extraction_config={"key": "gh_asserts_case_per_kloc"},
            description="Assertions per 1000 lines of code",
        ),
        # --- Git Team Features ---
        FeatureDefinition(
            key="gh_team_size",
            name="Team Size",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "gh_team_size"},
            description="Number of contributors in the team",
        ),
        FeatureDefinition(
            key="gh_by_core_team_member",
            name="By Core Member",
            data_type=FeatureDataType.BOOLEAN,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "gh_by_core_team_member"},
            description="Whether the build was triggered by a core team member",
        ),
        FeatureDefinition(
            key="gh_num_commits_on_files_touched",
            name="Commits on Files",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "gh_num_commits_on_files_touched"},
            description="Number of prior commits on the touched files",
        ),
        # --- Git History Features ---
        FeatureDefinition(
            key="git_prev_commit_resolution_status",
            name="Prev Commit Status",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "git_prev_commit_resolution_status"},
            description="Status of the previous commit resolution",
        ),
        FeatureDefinition(
            key="git_prev_built_commit",
            name="Prev Built Commit",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "git_prev_built_commit"},
            description="SHA of the previous built commit",
        ),
        FeatureDefinition(
            key="tr_prev_build",
            name="Prev Build ID",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "tr_prev_build"},
            description="ID of the previous build",
        ),
        FeatureDefinition(
            key="git_num_all_built_commits",
            name="Num Built Commits",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_EXTRACT,
            extraction_config={"key": "git_num_all_built_commits"},
            description="Number of built commits in history",
        ),
    ]

    # Upsert Features
    for feature in features:
        features_collection.update_one(
            {"key": feature.key}, {"$set": feature.dict(exclude={"id"})}, upsert=True
        )
    logger.info(f"Seeded {len(features)} features.")

    # 2. Define Template
    template = DatasetTemplate(
        name="TravisTorrent",
        description="Standard TravisTorrent dataset features",
        feature_keys=[f.key for f in features],
        default_mapping={
            "tr_build_id": "tr_build_id",
            "gh_project_name": "gh_project_name",
            "git_trigger_commit": "git_trigger_commit",
            "git_branch": "git_branch",
            "gh_lang": "gh_lang",
            "ci_provider": "ci_provider",
            "gh_build_started_at": "gh_build_started_at",
            "gh_is_pr": "gh_is_pr",
            "gh_pr_created_at": "gh_pr_created_at",
            "gh_pull_req_num": "gh_pull_req_num",
        },
    )

    templates_collection.update_one(
        {"name": template.name}, {"$set": template.dict(exclude={"id"})}, upsert=True
    )
    logger.info("Seeded TravisTorrent template.")


if __name__ == "__main__":
    seed_travistorrent()
