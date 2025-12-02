from __future__ import annotations

import logging
import time
import threading
from typing import List, Optional, Dict, Any, Tuple

from pymongo import ASCENDING
from app.config import settings
from buildguard_common.mongo import get_database

logger = logging.getLogger(__name__)


class Token:
    """Represents a GitHub API token with its rate limit state."""

    def __init__(self, token_str: str, remaining: int = 5000, reset_time: float = 0.0):
        self.key = token_str.strip()
        self.remaining = remaining
        self.reset_time = reset_time
        self.is_disabled = False

    def __repr__(self) -> str:
        return f"<Token {self.key[:4]}... Rem:{self.remaining}>"


class GitHubTokenService:
    """
    Token Manager backed by MongoDB.
    Directly queries MongoDB for token operations.
    """

    def __init__(self) -> None:
        self.db = get_database(settings.MONGODB_URI, settings.MONGODB_DB_NAME)
        self.collection = self.db["github_tokens"]
        self._ensure_indexes()
        self.pool_lock = threading.Lock()

    def _ensure_indexes(self):
        self.collection.create_index([("token", ASCENDING)], unique=True)
        self.collection.create_index("type")
        self.collection.create_index("disabled")

    def add_token(
        self, token_str: str, token_type: str = "pat", enable: bool = True
    ) -> bool:
        """Add a new token to MongoDB."""
        try:
            self.collection.update_one(
                {"token": token_str},
                {
                    "$set": {
                        "type": token_type,
                        "disabled": not enable,
                        "added_at": time.time(),
                        # Default values if new
                        "remaining": 5000,
                        "reset_time": 0.0,
                    }
                },
                upsert=True,
            )
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
                cursor = self.collection.find({"disabled": {"$ne": True}})
                docs = list(cursor)

                if not docs:
                    raise RuntimeError("No active tokens found in MongoDB.")

                available_candidates: List[Tuple[Dict[str, Any], int]] = []
                min_reset_time = float("inf")

                for doc in docs:
                    remaining = doc.get("remaining", 5000)
                    reset_time = doc.get("reset_time", 0.0)

                    # Track min reset time for sleeping
                    if reset_time < min_reset_time:
                        min_reset_time = reset_time

                    # Check if token is usable
                    # 1. Remaining > 0
                    # 2. OR Reset time has passed (treat as full)
                    if current_time > reset_time:
                        remaining = 5000

                    if remaining > 0:
                        available_candidates.append((doc, remaining))

                if available_candidates:
                    # Load balancing: pick one with max remaining
                    best_doc, _ = max(available_candidates, key=lambda x: x[1])

                    # Construct Token object
                    t = Token(
                        best_doc["token"],
                        remaining=best_doc.get("remaining", 5000),
                        reset_time=best_doc.get("reset_time", 0.0),
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
                self.collection.update_one({"token": token_key}, {"$set": updates})

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
            self.collection.update_one(
                {"token": token_key},
                {"$set": {"remaining": 0, "reset_time": new_reset}},
            )
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
            self.collection.update_one(
                {"token": token_key},
                {"$set": {"disabled": True, "disabled_at": time.time()}},
            )
            logger.info(f"🚫 Token {token_key[:4]}... disabled in MongoDB.")
        except Exception as e:
            logger.error(f"Failed to disable token in Mongo: {e}")

    def remove_token(self, token_key: str) -> bool:
        """Permanently remove token from MongoDB."""
        try:
            result = self.collection.delete_one({"token": token_key})
            if result.deleted_count > 0:
                logger.info(f"🗑️ Token {token_key[:4]}... removed from MongoDB.")
                return True
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
        cursor = self.collection.find().sort("added_at", -1)
        return [self._serialize(doc) for doc in cursor]

    def get_token(self, token_id: str) -> Optional[Dict[str, Any]]:
        from bson import ObjectId

        doc = self.collection.find_one({"_id": ObjectId(token_id)})
        return self._serialize(doc) if doc else None

    def _serialize(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        if not doc:
            return {}
        # Convert ObjectId to string
        if "_id" in doc:
            doc["id"] = str(doc.pop("_id"))
        return doc
