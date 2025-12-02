"""Common GitHub client wiring logic."""

from bson import ObjectId
from pymongo.database import Database
from redis import Redis

from buildguard_common import GitHubClient, GitHubTokenPool, GithubConfigurationError
from buildguard_common.github_auth import get_installation_token
from buildguard_common.repositories.base import CollectionName

_token_pool: GitHubTokenPool | None = None


def _client_with_api_url(
    api_url: str, token: str | None = None, token_pool: GitHubTokenPool | None = None
) -> GitHubClient:
    """Create a GitHubClient pointing to the configured API URL."""
    return GitHubClient(token=token, token_pool=token_pool, api_url=api_url)


def get_user_github_client(db: Database, user_id: str, api_url: str) -> GitHubClient:
    if not user_id:
        raise GithubConfigurationError("user_id is required for user auth")

    identity = db[CollectionName.OAUTH_IDENTITIES.value].find_one(
        {"user_id": ObjectId(user_id), "provider": "github"}
    )
    if not identity or not identity.get("access_token"):
        raise GithubConfigurationError(
            f"No GitHub OAuth token found for user {user_id}"
        )
    return _client_with_api_url(api_url=api_url, token=identity["access_token"])


def get_app_github_client(
    db: Database,
    installation_id: str,
    app_id: str | None,
    private_key: str | None,
    api_url: str,
    redis_client: Redis,
) -> GitHubClient:
    if not installation_id:
        raise GithubConfigurationError("installation_id is required for app auth")

    if not (app_id and private_key):
        raise GithubConfigurationError("GitHub App is not configured")

    token = get_installation_token(
        app_id=app_id,
        private_key=private_key,
        installation_id=installation_id,
        redis_client=redis_client,
        db=db,
        api_url=api_url,
    )
    return _client_with_api_url(api_url=api_url, token=token)


def get_public_github_client(tokens: list[str], api_url: str) -> GitHubClient:
    global _token_pool

    valid_tokens = [t for t in tokens if t and t.strip()]

    if not valid_tokens:
        raise GithubConfigurationError("No public GitHub tokens configured in settings")

    if len(valid_tokens) == 1:
        return _client_with_api_url(api_url=api_url, token=valid_tokens[0])

    snapshot = tuple(valid_tokens)
    if _token_pool is None or _token_pool.snapshot != snapshot:
        _token_pool = GitHubTokenPool(valid_tokens)

    return _client_with_api_url(api_url=api_url, token_pool=_token_pool)
