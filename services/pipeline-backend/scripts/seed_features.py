import asyncio
import logging
import sys
from typing import List

from pymongo import MongoClient, UpdateOne

# Add parent directory to path to allow imports from app
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.services.features.registry import registry
from buildguard_common.models.features import Feature, FeatureSourceType

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def map_source_type(source_value: str) -> FeatureSourceType:
    """Map backend FeatureSource string to common FeatureSourceType enum."""
    # Handle the mismatch identified in verification
    mapping = {
        "build_log": FeatureSourceType.BUILD_LOG,
        "git_history": FeatureSourceType.GIT_HISTORY,
        "repo_snapshot": FeatureSourceType.REPO_SNAPSHOT,
        "github_api": FeatureSourceType.GITHUB_API,
        "computed": FeatureSourceType.DERIVED,
    }
    # If exact match exists in target enum values, use it (for when they are aligned)
    if source_value in [e.value for e in FeatureSourceType]:
        return FeatureSourceType(source_value)

    return mapping.get(source_value, FeatureSourceType.DERIVED)


def seed_features():
    """Seed features from registry to database."""
    logger.info("Connecting to MongoDB...")
    client = MongoClient(settings.mongo.uri)
    db_name = os.getenv("MONGODB_DB_NAME", "buildguard")
    logger.info(f"Seeding into database: {db_name}")
    db = client[db_name]
    collection = db["features"]

    logger.info("Fetching features from registry...")
    registered_features = registry.list_features()

    operations = []
    for feat_dict in registered_features:
        # Convert registry dict to Feature model
        # registry.list_features returns dicts with: name, source, dependencies, description, group(optional)

        # Note: In registry, 'name' is the key (e.g. 'git_prev_commit_resolution_status')
        # We want to use this as 'key'.
        # For 'name' (display name), we'll generate a title case version if not available,
        # or we might need to update registry to support display names.
        # For now, let's use the key as the name but title-cased.

        key = feat_dict["name"]
        display_name = key.replace("_", " ").title()

        # Map source
        source_enum = map_source_type(feat_dict["source"])

        feature_model = Feature(
            key=key,
            name=display_name,
            description=feat_dict.get("description") or f"Feature {display_name}",
            data_type=feat_dict.get(
                "data_type", "string"
            ),  # Registry list_features doesn't return data_type currently!
            default_source=source_enum,
            dependencies=feat_dict.get("dependencies", []),
            is_active=True,
        )

        # We need to get data_type from the class itself because list_features doesn't include it
        feature_cls = registry.get(key)
        if feature_cls:
            feature_model.data_type = feature_cls.data_type

        # Prepare upsert
        operations.append(
            UpdateOne(
                {"key": key}, {"$set": feature_model.dict(exclude={"id"})}, upsert=True
            )
        )

    if operations:
        logger.info(f"Upserting {len(operations)} features...")
        result = collection.bulk_write(operations)
        logger.info(
            f"Seeding complete. Matched: {result.matched_count}, Modified: {result.modified_count}, Upserted: {result.upserted_count}"
        )
    else:
        logger.info("No features found to seed.")


if __name__ == "__main__":
    try:
        seed_features()
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        sys.exit(1)
