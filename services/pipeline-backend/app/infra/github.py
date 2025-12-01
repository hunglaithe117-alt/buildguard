"""GitHub client wiring for infrastructure layer."""

from bson import ObjectId
from pymongo.database import Database

from buildguard_common import GitHubClient, GitHubTokenPool, GithubConfigurationError

from app.core.config import settings
from app.services.github.github_app import github_app_configured, get_installation_token
)

_token_pool: GitHubTokenPool | None = None


def _client_with_api_url(
    token: str | None = None, token_pool: GitHubTokenPool | None = None
) -> GitHubClient:
    """Create a GitHubClient pointing to the configured API URL."""
    return GitHubClient(token=token, token_pool=token_pool, api_url=settings.github.api_url)


def get_user_github_client(db: Database, user_id: str) -> GitHubClient:
    if not user_id:
        raise GithubConfigurationError("user_id is required for user auth")

    identity = db.oauth_identities.find_one(
        {"user_id": ObjectId(user_id), "provider": "github"}
    )
    if not identity or not identity.get("access_token"):
        raise GithubConfigurationError(
            f"No GitHub OAuth token found for user {user_id}"
        )
    return _client_with_api_url(token=identity["access_token"])


def get_app_github_client(db: Database, installation_id: str) -> GitHubClient:
    if not installation_id:
        raise GithubConfigurationError("installation_id is required for app auth")

    if not github_app_configured():
        raise GithubConfigurationError("GitHub App is not configured")

    token = get_installation_token(installation_id, db=db)
    return _client_with_api_url(token=token)


def get_public_github_client() -> GitHubClient:
    global _token_pool

    tokens = settings.github.tokens or []
    tokens = [t for t in tokens if t and t.strip()]

    if not tokens:
        raise GithubConfigurationError("No public GitHub tokens configured in settings")

    if len(tokens) == 1:
        return _client_with_api_url(token=tokens[0])

    snapshot = tuple(tokens)
    if _token_pool is None or _token_pool.snapshot != snapshot:
        _token_pool = GitHubTokenPool(tokens)

    return _client_with_api_url(token_pool=_token_pool)
