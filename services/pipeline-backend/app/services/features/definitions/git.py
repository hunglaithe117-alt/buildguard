import logging
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from git import Commit, Repo

from app.domain.entities import ImportedRepository
from app.repositories import WorkflowRunRepository
from app.services.commit_replay import ensure_commit_exists
from app.services.extracts.diff_analyzer import (
    _count_test_cases,
    _is_doc_file,
    _is_source_file,
    _is_test_file,
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
class GitFeatureGroup(FeatureGroup):
    name = "git_group"
    source = FeatureSource.GIT_HISTORY
    features = {
        "git_prev_commit_resolution_status",
        "git_prev_built_commit",
        "tr_prev_build",
        "git_all_built_commits",
        "git_num_all_built_commits",
        "gh_team_size",
        "gh_by_core_team_member",
        "gh_num_commits_on_files_touched",
        "git_diff_src_churn",
        "git_diff_test_churn",
        "gh_diff_files_added",
        "gh_diff_files_deleted",
        "gh_diff_files_modified",
        "gh_diff_tests_added",
        "gh_diff_tests_deleted",
        "gh_diff_src_files",
        "gh_diff_doc_files",
        "gh_diff_other_files",
    }

    def setup(self, context: ExtractionContext) -> bool:
        if not context.repo or not context.build_sample.tr_original_commit:
            return False

        repo_path = REPOS_DIR / str(context.repo.id)
        context.set_cache("repo_path", repo_path)

        try:
            with repo_lock(str(context.repo.id)):
                self._ensure_repo(context.repo, repo_path)
                self._run_git(repo_path, ["fetch", "origin"])

                # Ensure commit exists
                token = self._get_token(context.repo)
                effective_sha = ensure_commit_exists(
                    repo_path,
                    context.build_sample.tr_original_commit,
                    context.repo.full_name,
                    token,
                )
                context.set_cache("effective_sha", effective_sha)

            if not effective_sha:
                return False

            git_repo = Repo(str(repo_path))
            context.set_cache("git_repo", git_repo)
            return True

        except Exception as e:
            logger.error(f"Setup failed for GitFeatureGroup: {e}")
            return False

    def extract_all(
        self, context: ExtractionContext, selected_features: Optional[Set[str]] = None
    ) -> Dict[str, FeatureResult]:
        # This method is optional if we implement individual features,
        # but the base class requires it. We can leave it empty or use it for bulk extraction.
        # Since we are moving to granular features, we will implement individual classes
        # and let the executor call them.
        # However, for optimization, we might want to compute shared things here if needed.
        # For now, we'll return empty dict as the executor will call individual features.
        return {}

    def _ensure_repo(self, repo: ImportedRepository, repo_path: Path):
        if repo_path.exists():
            if (repo_path / ".git").exists():
                return
            else:
                shutil.rmtree(repo_path)

        auth_url = f"https://github.com/{repo.full_name}.git"
        token = self._get_token(repo)

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

    def _get_token(self, repo: ImportedRepository) -> Optional[str]:
        if repo.installation_id:
            return get_installation_token(repo.installation_id, self.db)
        else:
            from app.core.config import settings

            tokens = settings.github.tokens
            if tokens and tokens[0]:
                return tokens[0]
        return None

    def _run_git(self, cwd: Path, args: List[str]) -> str:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()


# --- Shared Computation Helpers ---


def _compute_build_stats(context: ExtractionContext):
    if context.has_cache("build_stats"):
        return context.get_cache("build_stats")

    git_repo = context.get_cache("git_repo")
    commit_sha = context.get_cache("effective_sha")
    repo_id = context.build_sample.repo_id
    current_run_id = context.build_sample.workflow_run_id

    if not git_repo or not commit_sha:
        return {}

    try:
        build_commit = git_repo.commit(commit_sha)
    except Exception:
        return {}

    workflow_run_repo = WorkflowRunRepository(context.db)
    prev_commits_objs: List[Commit] = [build_commit]
    status = "no_previous_build"
    last_commit = None
    prev_build_id = None

    walker = git_repo.iter_commits(commit_sha, max_count=1000)
    first = True

    for commit in walker:
        if first:
            if len(commit.parents) > 1:
                status = "merge_found"
                break
            first = False
            continue

        last_commit = commit

        existing_build = workflow_run_repo.find_one(
            {
                "repo_id": repo_id,
                "head_sha": commit.hexsha,
                "status": "completed",
                "workflow_run_id": {"$ne": current_run_id},
            }
        )

        if existing_build:
            status = "build_found"
            prev_build_id = existing_build.run_number
            break

        prev_commits_objs.append(commit)

        if len(commit.parents) > 1:
            status = "merge_found"
            break

    commits_hex = [c.hexsha for c in prev_commits_objs]

    stats = {
        "git_prev_commit_resolution_status": status,
        "git_prev_built_commit": last_commit.hexsha if last_commit else None,
        "tr_prev_build": prev_build_id,
        "git_all_built_commits": commits_hex,
        "git_num_all_built_commits": len(commits_hex),
    }
    context.set_cache("build_stats", stats)
    return stats


def _compute_team_stats(context: ExtractionContext):
    if context.has_cache("team_stats"):
        return context.get_cache("team_stats")

    git_repo = context.get_cache("git_repo")
    commit_sha = context.get_cache("effective_sha")
    build_stats = _compute_build_stats(context)
    built_commits = build_stats.get("git_all_built_commits", [])

    if not git_repo or not built_commits:
        return {}

    ref_date = context.build_sample.gh_build_started_at
    if not ref_date:
        try:
            trigger_commit = git_repo.commit(built_commits[0])
            ref_date = datetime.fromtimestamp(trigger_commit.committed_date)
        except Exception:
            return {}

    start_date = ref_date - timedelta(days=90)

    # Helper to get direct committers
    def get_direct_committers(repo_path, start, end):
        import re

        pr_pattern = re.compile(r"\s\(#\d+\)")
        try:
            output = subprocess.run(
                [
                    "git",
                    "log",
                    "--first-parent",
                    "--no-merges",
                    f"--since={start.isoformat()}",
                    f"--until={end.isoformat()}",
                    "--format=%H|%an|%s",
                ],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except Exception:
            return set()

        direct = set()
        for line in output.splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            name, message = parts[1], parts[2]
            if pr_pattern.search(message) or "Merge pull request" in message:
                continue
            direct.add(name)
        return direct

    # Helper to get PR mergers
    def get_pr_mergers(repo_id, start, end):
        mergers = set()
        try:
            repo = WorkflowRunRepository(context.db)
            runs = repo.find_in_date_range(repo_id, start, end)
            for run in runs:
                payload = run.raw_payload
                if (
                    payload.get("pull_requests")
                    or payload.get("event") == "pull_request"
                ):
                    login = payload.get("triggering_actor", {}).get("login")
                    if login:
                        mergers.add(login)
        except Exception:
            pass
        return mergers

    committer_names = get_direct_committers(git_repo.working_dir, start_date, ref_date)
    merger_logins = get_pr_mergers(context.repo.id, start_date, ref_date)
    core_team = committer_names | merger_logins

    is_core_member = False
    try:
        trigger_commit = git_repo.commit(commit_sha)
        if (
            trigger_commit.author.name in core_team
            or trigger_commit.committer.name in core_team
        ):
            is_core_member = True
    except Exception:
        pass

    # Files Touched
    files_touched = set()
    for sha in built_commits:
        try:
            c = git_repo.commit(sha)
            if c.parents:
                for d in c.diff(c.parents[0]):
                    if d.b_path:
                        files_touched.add(d.b_path)
                    if d.a_path:
                        files_touched.add(d.a_path)
        except Exception:
            pass

    num_commits_on_files = 0
    if files_touched:
        try:
            all_shas = set()
            paths = list(files_touched)
            trigger_sha = built_commits[0]
            chunk_size = 50
            for i in range(0, len(paths), chunk_size):
                chunk = paths[i : i + chunk_size]
                out = git_repo.git.log(
                    trigger_sha,
                    "--since",
                    start_date.isoformat(),
                    "--format=%H",
                    "--",
                    *chunk,
                ).splitlines()
                all_shas.update(set(out))

            for sha in built_commits:
                if sha in all_shas:
                    all_shas.remove(sha)
            num_commits_on_files = len(all_shas)
        except Exception:
            pass

    stats = {
        "gh_team_size": len(core_team),
        "gh_by_core_team_member": is_core_member,
        "gh_num_commits_on_files_touched": num_commits_on_files,
    }
    context.set_cache("team_stats", stats)
    return stats


def _compute_diff_stats(context: ExtractionContext):
    if context.has_cache("diff_stats"):
        return context.get_cache("diff_stats")

    git_repo = context.get_cache("git_repo")
    current_commit = context.get_cache("effective_sha")
    build_stats = _compute_build_stats(context)
    built_commits = build_stats.get("git_all_built_commits", [])
    prev_built_commit = build_stats.get("git_prev_built_commit")

    if not git_repo or not built_commits:
        return {}

    stats = {
        "git_diff_src_churn": 0,
        "git_diff_test_churn": 0,
        "gh_diff_files_added": 0,
        "gh_diff_files_deleted": 0,
        "gh_diff_files_modified": 0,
        "gh_diff_tests_added": 0,
        "gh_diff_tests_deleted": 0,
        "gh_diff_src_files": 0,
        "gh_diff_doc_files": 0,
        "gh_diff_other_files": 0,
    }

    cwd = Path(git_repo.working_dir)

    def run_git(args):
        return subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True, check=True
        ).stdout.strip()

    for sha in built_commits:
        try:
            parent = run_git(["rev-parse", f"{sha}^"])
        except Exception:
            continue

        try:
            name_status = run_git(["diff", "--name-status", parent, sha])
            for line in name_status.splitlines():
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                status, path = parts[0][0], parts[-1]

                if status == "A":
                    stats["gh_diff_files_added"] += 1
                elif status == "D":
                    stats["gh_diff_files_deleted"] += 1
                elif status == "M":
                    stats["gh_diff_files_modified"] += 1

                if _is_doc_file(path):
                    stats["gh_diff_doc_files"] += 1
                elif _is_source_file(path) or _is_test_file(path):
                    stats["gh_diff_src_files"] += 1
                else:
                    stats["gh_diff_other_files"] += 1

            numstat = run_git(["diff", "--numstat", parent, sha])
            for line in numstat.splitlines():
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                try:
                    added = int(parts[0]) if parts[0] != "-" else 0
                    deleted = int(parts[1]) if parts[1] != "-" else 0
                except ValueError:
                    continue
                path = parts[2]

                if _is_source_file(path):
                    stats["git_diff_src_churn"] += added + deleted
                elif _is_test_file(path):
                    stats["git_diff_test_churn"] += added + deleted
        except Exception:
            continue

    if prev_built_commit:
        try:
            patch = run_git(["diff", prev_built_commit, current_commit])
            # Assuming we pick the first source language or default
            lang = (
                context.repo.source_languages[0].value.lower()
                if context.repo.source_languages
                else None
            )
            added_tests, deleted_tests = _count_test_cases(patch, lang)
            stats["gh_diff_tests_added"] = added_tests
            stats["gh_diff_tests_deleted"] = deleted_tests
        except Exception:
            pass

    context.set_cache("diff_stats", stats)
    return stats


# --- Individual Features ---


@register_feature
class GitPrevCommitResolutionStatus(BaseFeature):
    name = "git_prev_commit_resolution_status"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_build_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GitPrevBuiltCommit(BaseFeature):
    name = "git_prev_built_commit"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_build_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class TrPrevBuild(BaseFeature):
    name = "tr_prev_build"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_build_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GitAllBuiltCommits(BaseFeature):
    name = "git_all_built_commits"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_build_stats(context)
        return FeatureResult(self.name, stats.get(self.name, []))


@register_feature
class GitNumAllBuiltCommits(BaseFeature):
    name = "git_num_all_built_commits"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_build_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhTeamSize(BaseFeature):
    name = "gh_team_size"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_team_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhByCoreTeamMember(BaseFeature):
    name = "gh_by_core_team_member"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_team_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhNumCommitsOnFilesTouched(BaseFeature):
    name = "gh_num_commits_on_files_touched"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_team_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GitDiffSrcChurn(BaseFeature):
    name = "git_diff_src_churn"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_diff_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GitDiffTestChurn(BaseFeature):
    name = "git_diff_test_churn"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_diff_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhDiffFilesAdded(BaseFeature):
    name = "gh_diff_files_added"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_diff_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhDiffFilesDeleted(BaseFeature):
    name = "gh_diff_files_deleted"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_diff_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhDiffFilesModified(BaseFeature):
    name = "gh_diff_files_modified"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_diff_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhDiffTestsAdded(BaseFeature):
    name = "gh_diff_tests_added"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_diff_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhDiffTestsDeleted(BaseFeature):
    name = "gh_diff_tests_deleted"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_diff_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhDiffSrcFiles(BaseFeature):
    name = "gh_diff_src_files"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_diff_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhDiffDocFiles(BaseFeature):
    name = "gh_diff_doc_files"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_diff_stats(context)
        return FeatureResult(self.name, stats.get(self.name))


@register_feature
class GhDiffOtherFiles(BaseFeature):
    name = "gh_diff_other_files"
    source = FeatureSource.GIT_HISTORY

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_diff_stats(context)
        return FeatureResult(self.name, stats.get(self.name))
