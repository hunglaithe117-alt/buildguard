import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from pymongo.database import Database

from buildguard_common.models.github_public_token import GithubPublicToken
from buildguard_common.repositories.github_public_token import (
    GithubPublicTokenRepository,
)

logger = logging.getLogger(__name__)


class Token:
    """Represents a GitHub API token with its rate limit state (in-memory representation)."""

    def __init__(self, token_str: str, remaining: int = 5000, reset_time: float = 0.0):
        self.key = token_str.strip()
        self.remaining = remaining
        self.reset_time = reset_time
        self.is_disabled = False

    def __repr__(self) -> str:
        return f"<Token {self.key[:4]}... Rem:{self.remaining}>"


class GithubTokenService:
    """
    Token Manager backed by MongoDB (github_public_tokens).
    Directly queries MongoDB for token operations.
    """

    def __init__(self, db: Database) -> None:
        self.repo = GithubPublicTokenRepository(db)
        self.pool_lock = threading.Lock()

    def add_token(
        self, token_str: str, token_type: str = "pat", enable: bool = True
    ) -> bool:
        """Add a new token to MongoDB."""
        try:
            token = GithubPublicToken(
                token=token_str,
                type=token_type,
                disabled=not enable,
                added_at=time.time(),
                remaining=5000,
                reset_time=0.0,
            )
            self.repo.upsert_token(token)
            return True
        except Exception as e:
            logger.error(f"Failed to add token to Mongo: {e}")
            return False

    def get_best_token(self) -> Token:
        """
        Get the best available token from MongoDB.
        Blocking method: Waits until a usable token is available.
        """
        while True:
            with self.pool_lock:
                current_time = time.time()

                # Fetch all non-disabled tokens
                tokens = self.repo.find_available_tokens()

                if not tokens:
                    raise RuntimeError("No active tokens found in MongoDB.")

                available_candidates: List[Tuple[GithubPublicToken, int]] = []
                min_reset_time = float("inf")

                for token in tokens:
                    remaining = token.remaining
                    reset_time = token.reset_time

                    # Track min reset time for sleeping
                    if reset_time < min_reset_time:
                        min_reset_time = reset_time

                    # Check if token is usable
                    # 1. Remaining > 0
                    # 2. OR Reset time has passed (treat as full)
                    if current_time > reset_time:
                        remaining = 5000

                    if remaining > 0:
                        available_candidates.append((token, remaining))

                if available_candidates:
                    # Load balancing: pick one with max remaining
                    best_token, _ = max(available_candidates, key=lambda x: x[1])

                    # Construct Token object
                    t = Token(
                        best_token.token,
                        remaining=best_token.remaining,
                        reset_time=best_token.reset_time,
                    )

                    # If we assumed it reset, let's update the object state
                    if current_time > t.reset_time:
                        t.remaining = 5000

                    return t

                # If no tokens available, sleep
                wait_seconds = min_reset_time - current_time + 1.0
                if wait_seconds < 0:
                    wait_seconds = 1.0

                logger.warning(
                    f"⚠️ ALL TOKENS EXHAUSTED (Mongo). Sleeping {wait_seconds:.2f}s..."
                )

            # Sleep outside the lock
            time.sleep(wait_seconds)

    def update_token_status(self, token_key: str, headers: Any) -> None:
        """Update token status in MongoDB from response headers."""
        try:
            # headers keys are case-insensitive in requests
            remaining = headers.get("X-RateLimit-Remaining")
            reset = headers.get("X-RateLimit-Reset")

            updates: Dict[str, Any] = {}
            if remaining is not None:
                updates["remaining"] = int(remaining)
            if reset is not None:
                updates["reset_time"] = float(reset)

            updates["last_used"] = time.time()

            if updates:
                self.repo.update(
                    token_key, updates
                )  # Note: update expects ID or we need find_by_token first?
                # BaseRepository.update expects ID. But here we have token_key.
                # We should use update_one with query or find ID first.
                # Let's fix this in the repository or here.
                # Since BaseRepository is generic, let's use collection directly or add method to repo.

                # Better: add update_by_token to repository or use collection directly.
                # But we want to use repository pattern.
                token = self.repo.find_by_token(token_key)
                if token and token.id:
                    self.repo.update(token.id, updates)

                    # Log status for debugging
                    rem = updates.get("remaining", "?")
                    res = updates.get("reset_time", 0)
                    wait = int(res - time.time()) if res else 0
                    logger.debug(
                        f"🔄 Updated {token_key[:4]}... | Rem: {rem} | Resets in: {wait}s"
                    )

        except Exception as e:
            logger.error(f"Failed to update token {token_key[:4]}... in Mongo: {e}")

    def handle_rate_limit(self, token_key: str) -> None:
        """Handle 403/429 by setting remaining to 0 and backing off in Mongo."""
        try:
            # Force a cool-off period
            new_reset = time.time() + 60

            token = self.repo.find_by_token(token_key)
            if token and token.id:
                self.repo.update(token.id, {"remaining": 0, "reset_time": new_reset})
                logger.warning(
                    f"Token {token_key[:4]}... rate limited. Cooldown set in Mongo."
                )
        except Exception as e:
            logger.error(
                f"Failed to handle rate limit for {token_key[:4]}... in Mongo: {e}"
            )

    def disable_token(self, token_key: str) -> None:
        """Disable token in MongoDB."""
        try:
            token = self.repo.find_by_token(token_key)
            if token and token.id:
                self.repo.update(
                    token.id, {"disabled": True, "disabled_at": time.time()}
                )
                logger.info(f"🚫 Token {token_key[:4]}... disabled in MongoDB.")
        except Exception as e:
            logger.error(f"Failed to disable token in Mongo: {e}")

    def remove_token(self, token_key: str) -> bool:
        """Permanently remove token from MongoDB."""
        try:
            token = self.repo.find_by_token(token_key)
            if token and token.id:
                return self.repo.delete(token.id)
            else:
                logger.warning(
                    f"Token {token_key[:4]}... not found in MongoDB to remove."
                )
                return False
        except Exception as e:
            logger.error(f"Failed to remove token from Mongo: {e}")
            return False

    def list_tokens(self) -> List[Dict[str, Any]]:
        """List all tokens with their status."""
        # Return dicts for compatibility or models?
        # Existing service returned dicts via _serialize.
        # Let's return dicts to minimize changes in consumers.
        cursor = self.repo.collection.find().sort("added_at", -1)
        return [self.repo._serialize(doc) for doc in cursor]

    def get_token(self, token_id: str) -> Optional[Dict[str, Any]]:
        token = self.repo.find_by_id(token_id)
        if token:
            # Convert model to dict and handle ID
            d = token.model_dump(by_alias=True)
            if "_id" in d:
                d["id"] = str(d.pop("_id"))
            return d
        return None
