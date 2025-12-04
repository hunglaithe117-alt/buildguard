import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.repositories import WorkflowRunRepository
from app.services.features.base import (
    BaseFeature,
    ExtractionContext,
    FeatureGroup,
    FeatureResult,
    FeatureSource,
)
from app.services.features.registry import register_feature, register_group
from app.services.github.github_client import (
    get_app_github_client,
    get_public_github_client,
)

logger = logging.getLogger(__name__)


@register_group
class GitHubDiscussionFeatureGroup(FeatureGroup):
    name = "github_discussion_group"
    source = FeatureSource.GITHUB_API
    features = {
        "gh_num_commit_comments",
        "gh_num_pr_comments",
        "gh_num_issue_comments",
        "gh_description_complexity",
    }

    def setup(self, context: ExtractionContext) -> bool:
        # No specific setup needed as we fetch on demand or in shared computation
        return True

    def extract_all(
        self, context: ExtractionContext, selected_features: Optional[Set[str]] = None
    ) -> Dict[str, FeatureResult]:
        return {}


# --- Shared Computation Helpers ---


def _compute_discussion_stats(context: ExtractionContext):
    if context.has_cache("discussion_stats"):
        return context.get_cache("discussion_stats")

    workflow_run = context.workflow_run
    repo = context.repo
    build_sample = context.build_sample

    if not workflow_run or not repo:
        return {}

    commit_sha = build_sample.tr_original_commit or getattr(
        workflow_run, "head_sha", None
    )
    if not commit_sha:
        return {}

    # Calculate gh_description_complexity
    payload = workflow_run.raw_payload or {}
    pull_requests = payload.get("pull_requests", [])
    pr_number = None
    description_complexity = None

    if pull_requests:
        pr_data = pull_requests[0]
        pr_number = pr_data.get("number")
        title = pr_data.get("title", "")
        body = pr_data.get("body", "")
        description_complexity = len((title or "").split()) + len((body or "").split())
    elif payload.get("event") == "pull_request":
        pr_number = payload.get("number")

    installation_id = repo.installation_id

    try:
        from app.core.config import settings

        client_context = (
            get_app_github_client(
                context.db,
                installation_id,
                settings.github.app_id,
                settings.github.private_key,
                settings.github.api_url,
                None,  # redis_client, handled inside if needed or passed explicitly
            )
            if installation_id
            else get_public_github_client(
                settings.github.tokens, settings.github.api_url
            )
        )

        with client_context as gh:
            # Fetch PR details if complexity not yet calculated and we have a PR number
            if description_complexity is None and pr_number:
                try:
                    pr_details = gh.get_pull_request(repo.full_name, pr_number)
                    title = pr_details.get("title", "")
                    body = pr_details.get("body", "")
                    description_complexity = len((title or "").split()) + len(
                        (body or "").split()
                    )
                except Exception as e:
                    logger.warning(f"Failed to fetch PR details for complexity: {e}")

            # 1. Commit comments (Sum for all built commits)
            num_commit_comments = 0
            # We need built commits. If GitFeatureGroup ran, we might have them in cache.
            # But we can't rely on cross-group cache easily unless we enforce order.
            # For now, let's rely on build_sample data if available, or just check the trigger commit.
            # Ideally, GitFeatureGroup should run first.
            # Let's try to get from cache if available, else fallback to build_sample.

            # Check if we have git stats in cache (from GitFeatureGroup)
            git_stats = context.get_cache("build_stats")
            commits_to_check = []
            if git_stats:
                commits_to_check = git_stats.get("git_all_built_commits", [])

            if not commits_to_check and build_sample.git_all_built_commits:
                commits_to_check = build_sample.git_all_built_commits

            if not commits_to_check:
                commits_to_check = [commit_sha]

            # Deduplicate
            if isinstance(commits_to_check, str):
                commits_to_check = commits_to_check.split("#")
            commits_to_check = list(set(commits_to_check))

            for sha in commits_to_check:
                try:
                    comments = gh.list_commit_comments(repo.full_name, sha)
                    num_commit_comments += len(comments)
                except Exception as e:
                    logger.warning(f"Failed to fetch comments for commit {sha}: {e}")

            # 2. PR comments & Issue comments (Filtered by time window)
            num_pr_comments = 0
            num_issue_comments = 0

            if pr_number:
                end_time = build_sample.gh_build_started_at or datetime.now(
                    timezone.utc
                )
                start_time = None

                # Try to find previous build time
                if build_sample.tr_prev_build:
                    workflow_run_repo = WorkflowRunRepository(context.db)
                    # tr_prev_build is run_number usually
                    prev_run = workflow_run_repo.find_by_repo_and_run_id(
                        str(repo.id), build_sample.tr_prev_build
                    )
                    if prev_run and prev_run.created_at:
                        start_time = prev_run.created_at

                if not start_time:
                    # Fallback to PR creation time
                    if build_sample.gh_pr_created_at:
                        if isinstance(build_sample.gh_pr_created_at, str):
                            try:
                                start_time = datetime.fromisoformat(
                                    build_sample.gh_pr_created_at.replace("Z", "+00:00")
                                )
                            except ValueError:
                                pass
                        elif isinstance(build_sample.gh_pr_created_at, datetime):
                            start_time = build_sample.gh_pr_created_at

                if start_time and end_time:
                    if start_time.tzinfo is None:
                        start_time = start_time.replace(tzinfo=timezone.utc)
                    if end_time.tzinfo is None:
                        end_time = end_time.replace(tzinfo=timezone.utc)

                    # PR Review Comments
                    try:
                        reviews = gh.list_review_comments(repo.full_name, pr_number)
                        for comment in reviews:
                            created_at_str = comment.get("created_at")
                            if created_at_str:
                                created_at = datetime.fromisoformat(
                                    created_at_str.replace("Z", "+00:00")
                                )
                                if start_time <= created_at <= end_time:
                                    num_pr_comments += 1
                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch review comments for PR {pr_number}: {e}"
                        )

                    # Issue Comments
                    try:
                        issue_comments = gh.list_issue_comments(
                            repo.full_name, pr_number
                        )
                        for comment in issue_comments:
                            created_at_str = comment.get("created_at")
                            if created_at_str:
                                created_at = datetime.fromisoformat(
                                    created_at_str.replace("Z", "+00:00")
                                )
                                if start_time <= created_at <= end_time:
                                    num_issue_comments += 1
                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch issue comments for PR {pr_number}: {e}"
                        )

            stats = {
                "gh_num_commit_comments": num_commit_comments,
                "gh_num_pr_comments": num_pr_comments,
                "gh_num_issue_comments": num_issue_comments,
                "gh_description_complexity": description_complexity,
            }
            context.set_cache("discussion_stats", stats)
            return stats

    except Exception as e:
        logger.error(f"Failed to extract discussion features: {e}")
        return {}


# --- Individual Features ---


@register_feature
class GhNumCommitComments(BaseFeature):
    name = "gh_num_commit_comments"
    source = FeatureSource.GITHUB_API

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_discussion_stats(context)
        return FeatureResult(self.name, stats.get(self.name, 0))


@register_feature
class GhNumPrComments(BaseFeature):
    name = "gh_num_pr_comments"
    source = FeatureSource.GITHUB_API

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_discussion_stats(context)
        return FeatureResult(self.name, stats.get(self.name, 0))


@register_feature
class GhNumIssueComments(BaseFeature):
    name = "gh_num_issue_comments"
    source = FeatureSource.GITHUB_API

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_discussion_stats(context)
        return FeatureResult(self.name, stats.get(self.name, 0))


@register_feature
class GhDescriptionComplexity(BaseFeature):
    name = "gh_description_complexity"
    source = FeatureSource.GITHUB_API

    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        stats = _compute_discussion_stats(context)
        return FeatureResult(self.name, stats.get(self.name))
