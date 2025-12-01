import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)


class MissingForkCommitError(RuntimeError):
    """Raised when a commit only present on a fork cannot be reconstructed."""

    def __init__(self, commit_sha: str, message: str) -> None:
        self.commit_sha = commit_sha
        super().__init__(message)


@dataclass
class ReplayCommit:
    sha: str
    patch: str
    message: str
    author_name: str
    author_email: str
    author_date: str


@dataclass
class ReplayPlan:
    base_sha: str
    commits: List[ReplayCommit]


def ensure_commit_exists(
    repo_path: Path, commit_sha: str, repo_slug: str, token: Optional[str] = None
) -> Optional[str]:
    """
    Ensures that the given commit SHA exists in the local repository.
    If it's missing (e.g. from a fork), attempts to fetch it or reconstruct it.
    Returns the SHA to use (either the original if found, or a synthetic one).
    Returns None if failed.
    """
    if _commit_exists(repo_path, commit_sha):
        return commit_sha

    logger.info(
        f"Commit {commit_sha} not found locally. Attempting to fetch from origin..."
    )

    # Try fetching directly first (some servers allow fetching by SHA)
    try:
        _run_git(repo_path, ["fetch", "origin", commit_sha])
        if _commit_exists(repo_path, commit_sha):
            return commit_sha
    except subprocess.CalledProcessError:
        pass

    logger.info(
        f"Direct fetch failed. Attempting to replay fork commit {commit_sha}..."
    )

    try:
        plan = build_replay_plan(
            repo_slug=repo_slug,
            target_sha=commit_sha,
            commit_exists=lambda sha: _commit_exists(repo_path, sha),
            token=token,
        )
        synthetic_sha = apply_replay_plan(repo_path, plan, target_sha=commit_sha)
        return synthetic_sha
    except Exception as e:
        logger.error(f"Failed to replay commit {commit_sha}: {e}")
        return None


def build_replay_plan(
    repo_slug: str,
    target_sha: str,
    commit_exists: callable,
    token: Optional[str] = None,
    max_depth: int = 50,
) -> ReplayPlan:
    """
    Constructs a plan to replay missing commits by traversing up the ancestry
    until a locally existing commit is found.
    """
    if commit_exists(target_sha):
        raise ValueError(f"Commit {target_sha} already exists")

    missing_commits: List[ReplayCommit] = []
    current = target_sha
    depth = 0
    visited = set()

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "build-risk-ui/commit-replay",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    client = httpx.Client(headers=headers, timeout=30.0)

    try:
        while True:
            depth += 1
            if depth > max_depth:
                raise MissingForkCommitError(
                    target_sha, f"Exceeded parent traversal limit ({max_depth})"
                )

            # Get commit info
            try:
                resp = client.get(
                    f"https://api.github.com/repos/{repo_slug}/commits/{current}"
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as e:
                raise MissingForkCommitError(current, f"GitHub API error: {e}")

            parents = data.get("parents", [])
            if len(parents) != 1:
                # We can't easily replay merges or root commits without more complex logic
                # For now, fail if we hit a merge that is missing
                raise MissingForkCommitError(
                    current, "Cannot replay commit with zero or multiple parents"
                )

            parent_sha = parents[0]["sha"]

            # Get patch
            try:
                # Use specific accept header for patch
                patch_headers = headers.copy()
                patch_headers["Accept"] = "application/vnd.github.v3.patch"
                resp = client.get(
                    f"https://api.github.com/repos/{repo_slug}/commits/{current}",
                    headers=patch_headers,
                )
                resp.raise_for_status()
                patch_content = resp.text
            except httpx.HTTPError as e:
                raise MissingForkCommitError(current, f"Failed to download patch: {e}")

            commit_info = data.get("commit", {})
            author_info = commit_info.get("author", {})

            replay_commit = ReplayCommit(
                sha=current,
                patch=patch_content,
                message=commit_info.get("message", ""),
                author_name=author_info.get("name", "Unknown"),
                author_email=author_info.get("email", "unknown@example.com"),
                author_date=author_info.get("date", ""),
            )
            missing_commits.append(replay_commit)

            if commit_exists(parent_sha):
                missing_commits.reverse()
                logger.info(
                    f"Found base commit {parent_sha}. Replaying {len(missing_commits)} commits."
                )
                return ReplayPlan(base_sha=parent_sha, commits=missing_commits)

            if parent_sha in visited:
                raise MissingForkCommitError(current, "Loop detected")

            visited.add(current)
            current = parent_sha

    finally:
        client.close()


def apply_replay_plan(repo_path: Path, plan: ReplayPlan, target_sha: str) -> str:
    """
    Applies the replay plan by creating a temporary branch from the base commit,
    applying patches, creating commits.
    Returns the SHA of the final synthetic commit.
    """
    # Create a temp branch
    temp_branch = f"replay-{target_sha[:7]}"

    # Reset to base_sha on a new branch
    try:
        _run_git(repo_path, ["checkout", "-B", temp_branch, plan.base_sha])
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to checkout base commit {plan.base_sha}: {e}")

    last_sha = plan.base_sha

    for commit in plan.commits:
        logger.info(f"Replaying commit {commit.sha}...")

        # Apply patch
        try:
            subprocess.run(
                ["git", "apply", "--index", "--whitespace=nowarn"],
                cwd=repo_path,
                input=commit.patch,
                text=True,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to apply patch for {commit.sha}: {e.stderr}")

        # Commit
        env = {
            "GIT_AUTHOR_NAME": commit.author_name,
            "GIT_AUTHOR_EMAIL": commit.author_email,
            "GIT_AUTHOR_DATE": commit.author_date,
            "GIT_COMMITTER_NAME": "Antigravity Replay",
            "GIT_COMMITTER_EMAIL": "replay@antigravity.local",
        }

        cmd = ["git", "commit", "-m", commit.message]

        import os

        full_env = os.environ.copy()
        full_env.update(env)

        try:
            subprocess.run(
                cmd, cwd=repo_path, env=full_env, check=True, capture_output=True
            )
        except subprocess.CalledProcessError:
            # Try with --allow-empty if it failed (e.g. no changes)
            subprocess.run(
                cmd + ["--allow-empty"],
                cwd=repo_path,
                env=full_env,
                check=True,
                capture_output=True,
            )

        # Get the new SHA
        new_sha = _run_git(repo_path, ["rev-parse", "HEAD"])
        last_sha = new_sha

    logger.info(
        f"Replay complete. Synthetic commit is {last_sha}. Mapping {target_sha} -> {last_sha}"
    )
    return last_sha


def _run_git(cwd: Path, args: List[str]) -> str:
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _commit_exists(cwd: Path, sha: str) -> bool:
    try:
        subprocess.run(
            ["git", "cat-file", "-e", sha],
            cwd=cwd,
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False
