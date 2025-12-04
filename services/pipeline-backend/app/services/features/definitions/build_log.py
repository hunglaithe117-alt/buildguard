import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.services.extracts.log_parser import TestLogParser
from app.services.features.base import (
    BaseFeature,
    ExtractionContext,
    FeatureGroup,
    FeatureResult,
    FeatureSource,
)
from app.services.features.registry import register_feature, register_group

logger = logging.getLogger(__name__)


@register_group
class BuildLogFeatureGroup(FeatureGroup):
    name = "build_log_group"
    source = FeatureSource.BUILD_LOG
    features = {
        "tr_jobs",
        "tr_build_id",
        "tr_build_number",
        "tr_original_commit",
        "tr_log_lan_all",
        "tr_log_frameworks_all",
        "tr_log_num_jobs",
        "tr_log_tests_run_sum",
        "tr_log_tests_failed_sum",
        "tr_log_tests_skipped_sum",
        "tr_log_tests_ok_sum",
        "tr_log_tests_fail_rate",
        "tr_log_testduration_sum",
        "tr_status",
        "tr_duration",
    }

    def setup(self, context: ExtractionContext) -> bool:
        if not context.workflow_run or not context.repo:
            return False

        repo_id = str(context.build_sample.repo_id)
        run_id = str(context.build_sample.workflow_run_id)

        # Default log dir (should match what's in BuildLogExtractor)
        log_dir = Path("../repo-data/job_logs")
        run_log_dir = log_dir / repo_id / run_id

        if not run_log_dir.exists():
            logger.warning(f"No logs found for {repo_id}/{run_id}")
            return False

        log_files = list(run_log_dir.glob("*.log"))
        if not log_files:
            logger.warning(f"No log files found in {run_log_dir}")
            return False

        context.set_cache("log_files", log_files)
        return True

    def extract_all(
        self, context: ExtractionContext, selected_features: Optional[Set[str]] = None
    ) -> Dict[str, FeatureResult]:
        return {}


# --- Shared Computation Helpers ---


def _compute_log_stats(context: ExtractionContext):
    if context.has_cache("log_stats"):
        return context.get_cache("log_stats")

    log_files = context.get_cache("log_files")
    if not log_files:
        return {}

    parser = TestLogParser()

    tr_jobs = []
    frameworks = set()
    total_jobs = 0
    tests_run_sum = 0
    tests_failed_sum = 0
    tests_skipped_sum = 0
    tests_ok_sum = 0
    test_duration_sum = 0.0

    for log_file in log_files:
        try:
            job_id = int(log_file.stem)
            tr_jobs.append(job_id)
            total_jobs += 1

            content = log_file.read_text(errors="replace")
            parsed = parser.parse(content)

            if parsed.framework:
                frameworks.add(parsed.framework)

            tests_run_sum += parsed.tests_run
            tests_failed_sum += parsed.tests_failed
            tests_skipped_sum += parsed.tests_skipped
            tests_ok_sum += parsed.tests_ok

            if parsed.test_duration_seconds:
                test_duration_sum += parsed.test_duration_seconds

        except Exception as e:
            logger.error(f"Failed to parse log {log_file}: {e}")

    fail_rate = 0.0
    if tests_run_sum > 0:
        fail_rate = tests_failed_sum / tests_run_sum

    tr_status = "passed"
    if context.workflow_run.conclusion == "failure":
        tr_status = "failed"
    elif context.workflow_run.conclusion == "cancelled":
        tr_status = "cancelled"
    elif tests_failed_sum > 0:
        tr_status = "failed"

    tr_duration = 0.0
    if context.workflow_run.created_at and context.workflow_run.updated_at:
        delta = context.workflow_run.updated_at - context.workflow_run.created_at
        tr_duration = delta.total_seconds()

    stats = {
        "tr_jobs": tr_jobs,
        "tr_build_id": context.workflow_run.workflow_run_id,
        "tr_build_number": context.workflow_run.run_number,
        "tr_original_commit": context.workflow_run.head_sha,
        "tr_log_lan_all": context.repo.source_languages,
        "tr_log_frameworks_all": list(frameworks),
        "tr_log_num_jobs": total_jobs,
        "tr_log_tests_run_sum": tests_run_sum,
        "tr_log_tests_failed_sum": tests_failed_sum,
        "tr_log_tests_skipped_sum": tests_skipped_sum,
        "tr_log_tests_ok_sum": tests_ok_sum,
        "tr_log_tests_fail_rate": fail_rate,
        "tr_log_testduration_sum": test_duration_sum,
        "tr_status": tr_status,
        "tr_duration": tr_duration,
    }

    context.set_cache("log_stats", stats)
    return stats


# --- Individual Features ---


@register_feature
class TrJobs(BaseFeature):
    name = "tr_jobs"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name, []))


@register_feature
class TrBuildId(BaseFeature):
    name = "tr_build_id"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class TrBuildNumber(BaseFeature):
    name = "tr_build_number"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class TrOriginalCommit(BaseFeature):
    name = "tr_original_commit"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class TrLogLanAll(BaseFeature):
    name = "tr_log_lan_all"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name, []))


@register_feature
class TrLogFrameworksAll(BaseFeature):
    name = "tr_log_frameworks_all"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name, []))


@register_feature
class TrLogNumJobs(BaseFeature):
    name = "tr_log_num_jobs"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class TrLogTestsRunSum(BaseFeature):
    name = "tr_log_tests_run_sum"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class TrLogTestsFailedSum(BaseFeature):
    name = "tr_log_tests_failed_sum"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class TrLogTestsSkippedSum(BaseFeature):
    name = "tr_log_tests_skipped_sum"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class TrLogTestsOkSum(BaseFeature):
    name = "tr_log_tests_ok_sum"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class TrLogTestsFailRate(BaseFeature):
    name = "tr_log_tests_fail_rate"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class TrLogTestDurationSum(BaseFeature):
    name = "tr_log_testduration_sum"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class TrStatus(BaseFeature):
    name = "tr_status"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class TrDuration(BaseFeature):
    name = "tr_duration"
    source = FeatureSource.BUILD_LOG

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_log_stats(context)
        return FeatureResult(self.name, stats.get(self.name))
