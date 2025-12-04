import logging
import sys
from datetime import datetime

# Add paths to sys.path to ensure imports work
sys.path.append("/Users/hunglai/hust/20251/thesis/buildguard/services/pipeline-backend")
sys.path.append("/Users/hunglai/hust/20251/thesis/buildguard/packages")

from app.core.config import settings
from buildguard_common.mongo import get_database
from app.services.features.registry import registry
from buildguard_common.models.features import Feature
from buildguard_common.models.dataset_template import DatasetTemplate

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_features():
    logger.info("Starting feature seeding...")

    db = get_database(settings.mongo.uri, settings.mongo.database)
    feature_collection = db["features"]
    template_collection = db["dataset_templates"]

    # 1. Seed Features
    all_feature_keys = []

    features = registry.list_features()
    logger.info(f"Found {len(features)} features in registry.")

    for feat_meta in features:
        key = feat_meta["name"]
        feature_cls = registry.get(key)

        if not feature_cls:
            logger.warning(f"Could not find class for feature {key}")
            continue

        all_feature_keys.append(key)

        # Create or Update FeatureDefinition
        # We use the key as the unique identifier
        # Map FeatureSource to FeatureSourceType
        source_map = {
            "build_log": "build_log_extract",
            "git_history": "git_history_extract",
            "repo_snapshot": "repo_snapshot_extract",
            "github_api": "github_api_extract",
            "computed": "derived",
        }
        mapped_source = source_map.get(feature_cls.source.value, "derived")

        feature_def = Feature(
            key=key,
            name=key.replace("_", " ").title(),  # Simple name generation
            description=feat_meta["description"] or f"Feature {key}",
            data_type=feature_cls.data_type,
            default_source=mapped_source,
            dependencies=list(feature_cls.dependencies),
            is_active=True,
        )

        # Upsert
        result = feature_collection.update_one(
            {"key": key},
            {
                "$set": feature_def.dict(
                    exclude={"id", "created_at", "updated_at"}, exclude_none=True
                )
            },
            upsert=True,
        )

        if result.upserted_id:
            logger.info(f"Created feature: {key}")
        else:
            logger.info(f"Updated feature: {key}")

    # 2. Seed TravisTorrent Template
    template_name = "TravisTorrent"

    # Default mapping for TravisTorrent (example)
    # We can populate this more accurately if we know the CSV columns
    default_mapping = {key: key for key in all_feature_keys}

    template = DatasetTemplate(
        name=template_name,
        description="Standard TravisTorrent dataset template containing all available features.",
        feature_keys=all_feature_keys,
        default_mapping=default_mapping,
    )

    result = template_collection.update_one(
        {"name": template_name},
        {
            "$set": template.dict(
                exclude={"id", "created_at", "updated_at"}, exclude_none=True
            )
        },
        upsert=True,
    )

    if result.upserted_id:
        logger.info(f"Created template: {template_name}")
    else:
        logger.info(f"Updated template: {template_name}")

    logger.info("Seeding completed successfully.")


if __name__ == "__main__":
    seed_features()
