import sys
import os
from pprint import pprint

# Add paths
sys.path.append("/Users/hunglai/hust/20251/thesis/buildguard/services/app-backend")
sys.path.append("/Users/hunglai/hust/20251/thesis/buildguard/packages")

from app.config import settings
from buildguard_common.mongo import get_database
from app.services.dataset_builder_service import DatasetBuilderService


def verify_feature_loading():
    print("Verifying feature loading from DB...")

    # Connect to DB
    db = get_database(settings.MONGODB_URI, settings.MONGODB_DB_NAME)

    # Initialize Service
    service = DatasetBuilderService(db)

    # List features
    features = service.list_available_features()

    print(f"Found {len(features)} features.")

    if len(features) > 0:
        print("First 3 features:")
        pprint(features[:3])

        # Verify specific fields
        first = features[0]
        assert "name" in first
        assert "display_name" in first
        assert "source" in first
        assert "data_type" in first

        print(
            "\nVerification Successful: Features loaded from DB with correct structure."
        )
    else:
        print("\nVerification Failed: No features found.")


if __name__ == "__main__":
    verify_feature_loading()
