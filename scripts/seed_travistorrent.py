import logging
import os
import sys
from pathlib import Path
from typing import List

from pymongo import MongoClient

from buildguard_common.models.dataset_template import DatasetTemplate
from buildguard_common.models.feature import (
    FeatureDataType,
    FeatureDefinition,
    FeatureSourceType,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("MONGO_DATABASE", "buildguard")


def seed_travistorrent():
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]

    features_collection = db["feature_definitions"]
    templates_collection = db["dataset_templates"]

    # --- Feature Definitions ---
    features: List[FeatureDefinition] = [
        # Build metadata
        FeatureDefinition(
            key="tr_build_id",
            name="Build ID",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.BUILD_LOG,
            description="ID của bản build được phân tích, như được báo cáo.",
        ),
        FeatureDefinition(
            key="gh_project_name",
            name="GitHub Project Name",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Tên dự án trên GitHub.",
        ),
        FeatureDefinition(
            key="gh_is_pr",
            name="Is Pull Request",
            data_type=FeatureDataType.BOOLEAN,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Xác định build này có được kích hoạt từ một pull request hay không.",
        ),
        FeatureDefinition(
            key="gh_pr_created_at",
            name="PR Created At",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Nếu là pull request, thời gian tạo pull request đó (UTC).",
        ),
        FeatureDefinition(
            key="gh_pull_req_num",
            name="Pull Request Number",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Nếu là pull request, ID của pull request trên GitHub.",
        ),
        FeatureDefinition(
            key="gh_lang",
            name="Repository Language",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Ngôn ngữ chính của kho mã, theo GitHub.",
        ),
        FeatureDefinition(
            key="git_branch",
            name="Git Branch",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Nhánh được build.",
        ),
        FeatureDefinition(
            key="git_trigger_commit",
            name="Trigger Commit",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Commit đã kích hoạt build.",
        ),
        FeatureDefinition(
            key="gh_build_started_at",
            name="Build Started At",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Thời điểm build bắt đầu.",
        ),
        # Git history and lineage
        FeatureDefinition(
            key="git_prev_commit_resolution_status",
            name="Prev Commit Resolution Status",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Lý do dừng khi lần ngược lịch sử: no_previous_build, build_found hoặc merge_found.",
        ),
        FeatureDefinition(
            key="git_prev_built_commit",
            name="Prev Built Commit",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Commit đã kích hoạt bản build trước trong lịch sử tuyến tính.",
        ),
        FeatureDefinition(
            key="tr_prev_build",
            name="Previous Build",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Build được kích hoạt bởi git_prev_built_commit.",
        ),
        FeatureDefinition(
            key="git_all_built_commits",
            name="All Built Commits",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Danh sách (nối bằng #) commit từ commit build tới khi gặp build trước đó hoặc commit merge.",
        ),
        FeatureDefinition(
            key="git_num_all_built_commits",
            name="Num All Built Commits",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Số lượng commit trong git_all_built_commits.",
        ),
        # Team signals
        FeatureDefinition(
            key="gh_team_size",
            name="Team Size",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Số lượng lập trình viên đã commit trực tiếp hoặc merge PR trong vòng 3 tháng trước build.",
        ),
        FeatureDefinition(
            key="gh_by_core_team_member",
            name="By Core Team Member",
            data_type=FeatureDataType.BOOLEAN,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="true nếu tất cả tác giả trong git_all_built_commits thuộc core team 3 tháng gần build.",
        ),
        FeatureDefinition(
            key="gh_num_commits_on_files_touched",
            name="Num Commits On Files Touched",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Số commit duy nhất (không thuộc git_all_built_commits) trên các file bị tác động trong 3 tháng gần nhất.",
        ),
        # GitHub discussion signals
        FeatureDefinition(
            key="gh_num_commit_comments",
            name="Commit Comments",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GITHUB_API,
            description="Số lượng bình luận trên các commit trong git_all_built_commits trên GitHub.",
        ),
        FeatureDefinition(
            key="gh_num_pr_comments",
            name="PR Review Comments",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GITHUB_API,
            description="Số comment code review của PR trong khoảng thời gian quan sát.",
        ),
        FeatureDefinition(
            key="gh_num_issue_comments",
            name="PR Issue Comments",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GITHUB_API,
            description="Số comment thảo luận (issue_comments) của PR trong khoảng thời gian quan sát.",
        ),
        FeatureDefinition(
            key="gh_description_complexity",
            name="PR Description Complexity",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GITHUB_API,
            description="Tổng số từ trong tiêu đề và mô tả PR.",
        ),
        # Git diff / churn
        FeatureDefinition(
            key="git_diff_src_churn",
            name="Source Churn",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Tổng dòng thêm+bớt trong file code chính.",
        ),
        FeatureDefinition(
            key="git_diff_test_churn",
            name="Test Churn",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Tổng dòng thêm+bớt trong file test.",
        ),
        FeatureDefinition(
            key="gh_diff_files_added",
            name="Files Added",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Số file được thêm mới trong mọi commit thuộc git_all_built_commits.",
        ),
        FeatureDefinition(
            key="gh_diff_files_deleted",
            name="Files Deleted",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Số file bị xóa trong mọi commit thuộc git_all_built_commits.",
        ),
        FeatureDefinition(
            key="gh_diff_files_modified",
            name="Files Modified",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Số file được chỉnh sửa trong mọi commit thuộc git_all_built_commits.",
        ),
        FeatureDefinition(
            key="gh_diff_tests_added",
            name="Tests Added",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Số test case thêm trong mọi commit thuộc git_all_built_commits.",
        ),
        FeatureDefinition(
            key="gh_diff_tests_deleted",
            name="Tests Deleted",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Số lượng test case bị xóa trong mọi commit thuộc git_all_built_commits.",
        ),
        FeatureDefinition(
            key="gh_diff_src_files",
            name="Source Files Touched",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Số lượng file mã nguồn bị thay đổi trong mọi commit thuộc git_all_built_commits.",
        ),
        FeatureDefinition(
            key="gh_diff_doc_files",
            name="Doc Files Touched",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Số lượng file tài liệu bị thay đổi trong mọi commit thuộc git_all_built_commits.",
        ),
        FeatureDefinition(
            key="gh_diff_other_files",
            name="Other Files Touched",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.GIT_HISTORY,
            description="Số lượng file khác bị thay đổi trong mọi commit thuộc git_all_built_commits.",
        ),
        # Repository snapshot metrics
        FeatureDefinition(
            key="gh_sloc",
            name="Source Lines of Code",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Số dòng mã nguồn thực thi trong toàn bộ repository.",
        ),
        FeatureDefinition(
            key="gh_test_lines_per_kloc",
            name="Test Lines per KLOC",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Tổng số dòng mã test trên mỗi KLOC.",
        ),
        FeatureDefinition(
            key="gh_test_cases_per_kloc",
            name="Test Cases per KLOC",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Tổng số test case trên mỗi KLOC.",
        ),
        FeatureDefinition(
            key="gh_asserts_case_per_kloc",
            name="Asserts per KLOC",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Tổng số lệnh assert trên mỗi KLOC.",
        ),
        FeatureDefinition(
            key="gh_repo_age",
            name="Repository Age",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Tuổi của repository tính bằng ngày.",
        ),
        FeatureDefinition(
            key="gh_repo_num_commits",
            name="Repository Num Commits",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.REPO_SNAPSHOT,
            description="Số commit tính từ commit kích hoạt build ngược tới commit đầu tiên.",
        ),
        # Build log metrics
        FeatureDefinition(
            key="tr_jobs",
            name="Job IDs",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.BUILD_LOG,
            description="ID của job trong build được phân tích.",
        ),
        FeatureDefinition(
            key="tr_build_number",
            name="Build Number",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.BUILD_LOG,
            description="Số thứ tự của build trong dự án.",
        ),
        FeatureDefinition(
            key="tr_original_commit",
            name="Original Commit",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.BUILD_LOG,
            description="SHA của commit.",
        ),
        FeatureDefinition(
            key="tr_log_lan_all",
            name="Log Languages",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.BUILD_LOG,
            description="Các ngôn ngữ chính trích xuất từ log build.",
        ),
        FeatureDefinition(
            key="tr_log_frameworks_all",
            name="Log Frameworks",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.BUILD_LOG,
            description="Các test framework xuất hiện trong log.",
        ),
        FeatureDefinition(
            key="tr_log_tests_run_sum",
            name="Tests Run Sum",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.BUILD_LOG,
            description="Tổng số test được chạy trong toàn bộ build.",
        ),
        FeatureDefinition(
            key="tr_log_tests_failed_sum",
            name="Tests Failed Sum",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.BUILD_LOG,
            description="Tổng số test bị lỗi trong toàn bộ build.",
        ),
        FeatureDefinition(
            key="tr_log_tests_skipped_sum",
            name="Tests Skipped Sum",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.BUILD_LOG,
            description="Tổng số test bị bỏ qua trong toàn bộ build.",
        ),
        FeatureDefinition(
            key="tr_log_tests_ok_sum",
            name="Tests OK Sum",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.BUILD_LOG,
            description="Tổng số test thành công trong toàn bộ build.",
        ),
        FeatureDefinition(
            key="tr_log_tests_fail_rate",
            name="Test Fail Rate",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.BUILD_LOG,
            description="Tỷ lệ test thất bại trong build.",
        ),
        FeatureDefinition(
            key="tr_log_testduration_sum",
            name="Test Duration Sum",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.BUILD_LOG,
            description="Tổng thời gian test của các job.",
        ),
        FeatureDefinition(
            key="tr_status",
            name="Build Status",
            data_type=FeatureDataType.STRING,
            default_source=FeatureSourceType.BUILD_LOG,
            description="Trạng thái tổng thể của build (thành công/thất bại/lỗi).",
        ),
        FeatureDefinition(
            key="tr_duration",
            name="Build Duration",
            data_type=FeatureDataType.FLOAT,
            default_source=FeatureSourceType.BUILD_LOG,
            description="Tổng thời gian build (bao gồm thiết lập, build và test).",
        ),
        FeatureDefinition(
            key="tr_log_num_jobs",
            name="Num Jobs",
            data_type=FeatureDataType.INTEGER,
            default_source=FeatureSourceType.BUILD_LOG,
            description="Tổng số jobs trong build.",
        ),
    ]

    for feature in features:
        features_collection.update_one(
            {"key": feature.key},
            {"$set": feature.to_mongo()},
            upsert=True,
        )
    logger.info("Seeded %s features.", len(features))

    feature_keys = [f.key for f in features]
    template = DatasetTemplate(
        name="TravisTorrent",
        description="Standard TravisTorrent dataset features.",
        feature_keys=feature_keys,
        default_mapping={key: key for key in feature_keys},
    )

    templates_collection.update_one(
        {"name": template.name},
        {"$set": template.to_mongo()},
        upsert=True,
    )
    logger.info("Seeded TravisTorrent template.")


if __name__ == "__main__":
    seed_travistorrent()
