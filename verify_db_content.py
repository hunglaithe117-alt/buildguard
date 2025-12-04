import os
import sys
from pprint import pprint
from buildguard_common.mongo import get_database
from app.core.config import settings


def verify_db():
    print("Verifying DB content...")
    db = get_database(settings.mongo.uri, settings.mongo.database)

    features_coll = db["features"]
    count = features_coll.count_documents({})
    print(f"Total features: {count}")

    # Check for dependencies
    sample = features_coll.find_one(
        {"dependencies": {"$exists": True, "$not": {"$size": 0}}}
    )
    if sample:
        print("Found feature with dependencies:")
        pprint(sample)
    else:
        print(
            "No features with dependencies found (might be expected if none have them yet)."
        )

    # Check one random feature
    print("\nRandom feature:")
    pprint(features_coll.find_one())


if __name__ == "__main__":
    verify_db()
