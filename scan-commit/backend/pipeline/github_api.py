from __future__ import annotations

import logging
import threading
import time
from typing import List, Optional
from urllib.parse import quote

import requests

from app.core.config import settings

LOG = logging.getLogger("pipeline.github")


import hashlib
import json
import redis
from app.services.github_token_service import GitHubTokenService

LOG = logging.getLogger("pipeline.github")


class GitHubAPIError(RuntimeError):
    """Raised when the GitHub API returns an error response."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)


class GitHubRateLimitError(GitHubAPIError):
    def __init__(self, retry_at: float, message: str) -> None:
        super().__init__(403, message)
        self.retry_at = retry_at


class GitHubAPI:
    """Wrapper around GitHub API with Mongo-backed Token Manager and Redis Caching."""

    def __init__(self, base_url: str, *, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.token_service = GitHubTokenService()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "build-commit-pipeline/sonar",
        })
        self.timeout = timeout
        
        # Initialize Redis for Caching
        # We use the same Redis URL as Celery/App
        self.redis = redis.from_url(settings.redis.url)
        self.cache_ttl = 3600 * 24 * 7  # 7 days cache

    def _get_cache_key(self, url: str, params: Optional[dict]) -> str:
        key_str = f"{url}:{json.dumps(params, sort_keys=True)}"
        hashed = hashlib.md5(key_str.encode()).hexdigest()
        return f"github:cache:{hashed}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        accept: str,
        params: Optional[dict[str, str]] = None,
    ) -> requests.Response:
        url = f"{self.base_url}{path}"
        errors: list[str] = []
        
        # Check Cache (only for GET)
        cache_key = None
        etag = None
        if method == "GET":
            cache_key = self._get_cache_key(url, params)
            cached_raw = self.redis.get(cache_key)
            if cached_raw:
                try:
                    cached_data = json.loads(cached_raw)
                    etag = cached_data.get("etag")
                except Exception:
                    pass

        attempts = 0
        # Try a reasonable number of times (e.g., 5) to get a working token
        max_attempts = 5
        
        while attempts < max_attempts:
            attempts += 1
            try:
                token_obj = self.token_service.get_best_token()
                token = token_obj.key
            except RuntimeError as exc:
                # All tokens exhausted/disabled
                raise GitHubRateLimitError(
                    retry_at=time.time() + 60,
                    message=str(exc),
                ) from exc

            headers = {
                "Accept": accept,
                "Authorization": f"token {token}",
            }
            if etag:
                headers["If-None-Match"] = etag

            try:
                LOG.info(f"🚀 Using token {token[:4]}... for {method} {url}")
                resp = self.session.request(
                    method,
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
                
                # Update Token Status
                self.token_service.update_token_status(token, resp.headers)

                # Handle 304 Not Modified
                if resp.status_code == 304 and cache_key:
                    LOG.info(f"⚡ 304 Not Modified for {url}. Using Redis cache.")
                    cached_raw = self.redis.get(cache_key)
                    if cached_raw:
                        cached_data = json.loads(cached_raw)
                        # Reconstruct response
                        resp.status_code = 200
                        resp._content = json.dumps(cached_data["data"]).encode("utf-8")
                        return resp

                # Handle 401 Invalid Token
                if resp.status_code == 401:
                    LOG.error(f"🚫 Token {token[:4]}... is INVALID (401). Removing.")
                    self.token_service.remove_token(token)
                    continue

                # Handle 403/429 Rate Limits
                if resp.status_code == 429 or (
                    resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0"
                ):
                    LOG.warning(f"❌ Rate Limit Exceeded ({resp.status_code}). Token {token[:4]}... exhausted.")
                    self.token_service.handle_rate_limit(token)
                    continue

                # Handle Spammy/Abuse
                if 400 < resp.status_code < 500 and "spammy" in resp.text.lower():
                     LOG.warning(f"🚫 Token {token[:4]}... flagged as spammy.")
                     self.token_service.disable_token(token)
                     continue

                # Cache Successful GET Responses
                if resp.status_code == 200 and cache_key:
                    new_etag = resp.headers.get("ETag")
                    if new_etag:
                        try:
                            cache_data = {
                                "etag": new_etag,
                                "data": resp.json()
                            }
                            self.redis.setex(cache_key, self.cache_ttl, json.dumps(cache_data))
                        except Exception as e:
                            LOG.warning(f"Failed to cache response: {e}")

                if resp.status_code >= 400:
                    snippet = (resp.text or "")[:200]
                    message = f"GitHub API {resp.status_code} for {path}: {snippet}"
                    raise GitHubAPIError(resp.status_code, message)
                
                return resp

            except requests.RequestException as exc:
                errors.append(str(exc))
                continue
        
        raise GitHubAPIError(503, "All GitHub API attempts failed: " + "; ".join(errors))

    @staticmethod
    def _encode_slug(repo_slug: str) -> str:
        return quote(repo_slug, safe="/")

    def get_commit(self, repo_slug: str, commit_sha: str) -> dict:
        slug = self._encode_slug(repo_slug)
        resp = self._request(
            "GET",
            f"/repos/{slug}/commits/{commit_sha}",
            accept="application/vnd.github+json",
        )
        return resp.json()

    def get_commit_patch(self, repo_slug: str, commit_sha: str) -> str:
        slug = self._encode_slug(repo_slug)
        resp = self._request(
            "GET",
            f"/repos/{slug}/commits/{commit_sha}",
            accept="application/vnd.github.v3.patch",
        )
        return resp.text


_CLIENT: Optional[GitHubAPI] = None


def get_github_client() -> Optional[GitHubAPI]:
    """Return a cached GitHub client instance."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    
    # We no longer rely on settings.github.tokens for initialization
    # The service will pull from MongoDB
    
    _CLIENT = GitHubAPI(
        base_url=getattr(settings.github, "api_url", "https://api.github.com"),
    )
    return _CLIENT
