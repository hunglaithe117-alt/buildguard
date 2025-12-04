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
    feature_collection = db["features"]
    template_collection = db["dataset_templates"]

    logger.info("Fetching features from registry...")
    registered_features = registry.list_features()

    key_to_id_map = {}
    operations = []

    # 1. Seed Features
    for feat_dict in registered_features:
        key = feat_dict["name"]
        display_name = key.replace("_", " ").title()
        source_enum = map_source_type(feat_dict["source"])

        feature_model = Feature(
            key=key,
            name=display_name,
            description=feat_dict.get("description") or f"Feature {display_name}",
            data_type=feat_dict.get("data_type", "string"),
            default_source=source_enum,
            dependencies=feat_dict.get("dependencies", []),
            is_active=True,
        )

        feature_cls = registry.get(key)
        if feature_cls:
            feature_model.data_type = feature_cls.data_type

        # Upsert feature
        feature_collection.update_one(
            {"key": key}, {"$set": feature_model.dict(exclude={"id"})}, upsert=True
        )

        # Retrieve the ID
        saved_feat = feature_collection.find_one({"key": key}, {"_id": 1})
        if saved_feat:
            key_to_id_map[key] = saved_feat["_id"]

    logger.info(f"Synced {len(key_to_id_map)} features.")

    # 2. Seed TravisTorrent Template with IDs
    template_name = "TravisTorrent"
    feature_ids = list(key_to_id_map.values())

    template_data = {
        "name": template_name,
        "description": "Standard TravisTorrent dataset template.",
        "feature_ids": feature_ids,
        "default_mapping": {},  # Can be populated if we have default CSV columns
    }

    template_collection.update_one(
        {"name": template_name}, {"$set": template_data}, upsert=True
    )
    logger.info(f"Seeded template '{template_name}' with {len(feature_ids)} features.")
    logger.info("Seeding complete.")


if __name__ == "__main__":
    try:
        seed_features()
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        sys.exit(1)
