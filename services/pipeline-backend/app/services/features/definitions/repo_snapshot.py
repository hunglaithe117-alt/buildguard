import logging
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

from app.services.commit_replay import ensure_commit_exists
from app.services.extracts.diff_analyzer import (
    _is_source_file,
    _is_test_file,
    _matches_assertion,
    _matches_test_definition,
    _strip_comments,
)
from app.services.features.base import (
    BaseFeature,
    ExtractionContext,
    FeatureGroup,
    FeatureResult,
    FeatureSource,
)
from app.services.features.registry import register_feature, register_group
from app.services.github.github_app import get_installation_token
from buildguard_common.utils.locking import repo_lock

logger = logging.getLogger(__name__)

REPOS_DIR = Path("../repo-data/repos")
REPOS_DIR.mkdir(parents=True, exist_ok=True)


@register_group
class RepoSnapshotFeatureGroup(FeatureGroup):
    name = "repo_snapshot_group"
    source = FeatureSource.REPO_SNAPSHOT
    features = {
        "gh_repo_age",
        "gh_repo_num_commits",
        "gh_sloc",
        "gh_test_lines_per_kloc",
        "gh_test_cases_per_kloc",
        "gh_asserts_case_per_kloc",
        "gh_project_name",
        "gh_is_pr",
        "gh_pr_created_at",
        "gh_pull_req_num",
        "gh_lang",
        "git_branch",
        "git_trigger_commit",
        "gh_build_started_at",
    }

    def setup(self, context: ExtractionContext) -> bool:
        # We can reuse the repo setup from GitFeatureGroup if it ran.
        # But we must ensure it's there.
        if not context.repo:
            return False

        repo_path = REPOS_DIR / str(context.repo.id)
        context.set_cache("repo_path", repo_path)

        # If GitFeatureGroup ran, 'effective_sha' might be in cache.
        if not context.has_cache("effective_sha"):
            commit_sha = context.build_sample.tr_original_commit
            if not commit_sha:
                return False

            try:
                with repo_lock(str(context.repo.id)):
                    self._ensure_repo(context, repo_path)
                    # We might need to fetch if not already done
                    # But ideally GitFeatureGroup handles this.
                    # For safety, let's assume if repo exists we are good, or we try to ensure commit.
                    token = self._get_token(context)
                    effective_sha = ensure_commit_exists(
                        repo_path, commit_sha, context.repo.full_name, token
                    )
                    context.set_cache("effective_sha", effective_sha)
            except Exception as e:
                logger.error(f"Setup failed for RepoSnapshotFeatureGroup: {e}")
                return False

        return True

    def extract_all(
        self, context: ExtractionContext, selected_features: Optional[Set[str]] = None
    ) -> Dict[str, FeatureResult]:
        return {}

    def _ensure_repo(self, context: ExtractionContext, repo_path: Path):
        if repo_path.exists():
            if (repo_path / ".git").exists():
                return
            else:
                shutil.rmtree(repo_path)

        repo = context.repo
        auth_url = f"https://github.com/{repo.full_name}.git"
        token = self._get_token(context)

        if token:
            if repo.installation_id:
                auth_url = (
                    f"https://x-access-token:{token}@github.com/{repo.full_name}.git"
                )
            else:
                auth_url = f"https://{token}@github.com/{repo.full_name}.git"

        logger.info(f"Cloning {repo.full_name} to {repo_path}")
        subprocess.run(
            ["git", "clone", auth_url, str(repo_path)],
            check=True,
            capture_output=True,
        )

    def _get_token(self, context: ExtractionContext) -> Optional[str]:
        repo = context.repo
        if repo.installation_id:
            return get_installation_token(repo.installation_id, context.db)
        else:
            from app.core.config import settings

            tokens = settings.github.tokens
            if tokens and tokens[0]:
                return tokens[0]
        return None


# --- Shared Computation Helpers ---


def _compute_snapshot_stats(context: ExtractionContext):
    if context.has_cache("snapshot_stats"):
        return context.get_cache("snapshot_stats")

    repo_path = context.get_cache("repo_path")
    effective_sha = context.get_cache("effective_sha")
    repo = context.repo
    workflow_run = context.workflow_run

    if not repo_path or not effective_sha or not repo:
        return {}

    stats = {}

    # Metadata fields
    payload = workflow_run.raw_payload or {} if workflow_run else {}
    head_branch = payload.get("head_branch")
    pull_requests = payload.get("pull_requests", [])
    is_pr = len(pull_requests) > 0 or payload.get("event") == "pull_request"

    pr_number = None
    pr_created_at = None

    if pull_requests:
        pr_data = pull_requests[0]
        pr_number = pr_data.get("number")
        pr_created_at = pr_data.get("created_at")

    stats.update(
        {
            "gh_project_name": repo.full_name,
            "gh_is_pr": is_pr,
            "gh_pr_created_at": pr_created_at,
            "gh_pull_req_num": pr_number,
            "gh_lang": repo.main_lang,
            "git_branch": head_branch,
            "git_trigger_commit": effective_sha,
            "gh_build_started_at": workflow_run.created_at if workflow_run else None,
        }
    )

    # 1. History metrics (Age, Num Commits)
    try:
        age, num_commits = _get_history_metrics(repo_path, effective_sha)
        stats["gh_repo_age"] = age
        stats["gh_repo_num_commits"] = num_commits
    except Exception as e:
        logger.warning(f"Failed to get history metrics: {e}")

    # 2. Snapshot metrics (SLOC, Tests) using worktree
    try:
        raw_stats = {"sloc": 0, "test_lines": 0, "test_cases": 0, "asserts": 0}
        with repo_lock(str(repo.id)):
            for source_lang in repo.source_languages:
                lang_stats = _analyze_snapshot_raw(
                    repo_path, effective_sha, source_lang.value.lower()
                )
                raw_stats["sloc"] += lang_stats["sloc"]
                raw_stats["test_lines"] += lang_stats["test_lines"]
                raw_stats["test_cases"] += lang_stats["test_cases"]
                raw_stats["asserts"] += lang_stats["asserts"]

        stats["gh_sloc"] = raw_stats["sloc"]
        if raw_stats["sloc"] > 0:
            kloc = raw_stats["sloc"] / 1000.0
            stats["gh_test_lines_per_kloc"] = raw_stats["test_lines"] / kloc
            stats["gh_test_cases_per_kloc"] = raw_stats["test_cases"] / kloc
            stats["gh_asserts_case_per_kloc"] = raw_stats["asserts"] / kloc
        else:
            stats["gh_test_lines_per_kloc"] = 0.0
            stats["gh_test_cases_per_kloc"] = 0.0
            stats["gh_asserts_case_per_kloc"] = 0.0

    except Exception as e:
        logger.warning(f"Failed to get snapshot metrics: {e}")

    context.set_cache("snapshot_stats", stats)
    return stats


def _get_history_metrics(repo_path: Path, commit_sha: str) -> Tuple[float, int]:
    def run_git(args):
        return subprocess.run(
            ["git"] + args, cwd=repo_path, capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        count_out = run_git(["rev-list", "--count", commit_sha])
        num_commits = int(count_out)
    except (subprocess.CalledProcessError, ValueError):
        num_commits = 0

    try:
        current_ts = run_git(["show", "-s", "--format=%ct", commit_sha])
        roots = run_git(["rev-list", "--max-parents=0", commit_sha]).splitlines()
        if roots:
            root_sha = roots[-1]
            first_ts = run_git(["show", "-s", "--format=%ct", root_sha])
            age_seconds = int(current_ts) - int(first_ts)
            age_days = max(0.0, age_seconds / 86400.0)
        else:
            age_days = 0.0
    except (subprocess.CalledProcessError, ValueError):
        age_days = 0.0

    return age_days, num_commits


def _analyze_snapshot_raw(
    repo_path: Path, commit_sha: str, language: str | None
) -> Dict[str, int]:
    stats = {
        "sloc": 0,
        "test_lines": 0,
        "test_cases": 0,
        "asserts": 0,
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        worktree_path = Path(tmp_dir) / "worktree"
        try:
            subprocess.run(
                ["git", "worktree", "add", "-f", str(worktree_path), commit_sha],
                cwd=repo_path,
                check=True,
                capture_output=True,
            )

            for file_path in worktree_path.rglob("*"):
                if not file_path.is_file():
                    continue
                if ".git" in file_path.parts:
                    continue

                rel_path = str(file_path.relative_to(worktree_path))

                try:
                    with open(file_path, "r", errors="ignore") as f:
                        lines = f.readlines()
                        line_count = len(lines)
                        content = "".join(lines)

                    if _is_test_file(rel_path):
                        stats["test_lines"] += line_count
                        stats["test_cases"] += _count_tests(content, language)
                        stats["asserts"] += _count_asserts(content, language)
                    elif _is_source_file(rel_path):
                        stats["sloc"] += line_count

                except Exception:
                    pass

        finally:
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "-f", str(worktree_path)],
                    cwd=repo_path,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "worktree", "prune"],
                    cwd=repo_path,
                    capture_output=True,
                )
            except Exception:
                pass

    return stats


def _count_tests(content: str, language: str | None) -> int:
    count = 0
    lang = (language or "").lower()
    for line in content.splitlines():
        clean_line = _strip_comments(line, lang)
        if _matches_test_definition(clean_line, lang):
            count += 1
    return count


def _count_asserts(content: str, language: str | None) -> int:
    count = 0
    lang = (language or "").lower()
    for line in content.splitlines():
        clean_line = _strip_comments(line, lang)
        if _matches_assertion(clean_line, lang):
            count += 1
    return count


# --- Individual Features ---


@register_feature
class GhRepoAge(BaseFeature):
    name = "gh_repo_age"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhRepoNumCommits(BaseFeature):
    name = "gh_repo_num_commits"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhSloc(BaseFeature):
    name = "gh_sloc"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhTestLinesPerKloc(BaseFeature):
    name = "gh_test_lines_per_kloc"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhTestCasesPerKloc(BaseFeature):
    name = "gh_test_cases_per_kloc"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhAssertsCasePerKloc(BaseFeature):
    name = "gh_asserts_case_per_kloc"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhProjectName(BaseFeature):
    name = "gh_project_name"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhIsPr(BaseFeature):
    name = "gh_is_pr"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhPrCreatedAt(BaseFeature):
    name = "gh_pr_created_at"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhPullReqNum(BaseFeature):
    name = "gh_pull_req_num"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhLang(BaseFeature):
    name = "gh_lang"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GitBranch(BaseFeature):
    name = "git_branch"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GitTriggerCommit(BaseFeature):
    name = "git_trigger_commit"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhBuildStartedAt(BaseFeature):
    name = "gh_build_started_at"
    source = FeatureSource.REPO_SNAPSHOT

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_snapshot_stats(context)
        return FeatureResult(self.name, stats.get(self.name))
