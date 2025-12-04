import sys
import os
from pathlib import Path

# Add services/pipeline-backend to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from pymongo import MongoClient
from app.services.features.registry import registry
from app.services.features.base import ExtractionContext
from app.domain.entities import BuildSample, ImportedRepository, WorkflowRunRaw

# Connect to DB
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
db = client["buildguard"]

# Initialize Redis
from buildguard_common.redis_client import get_redis

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
get_redis(redis_url)
print(f"Initialized Redis at {redis_url}")


def verify_features():
    print("Verifying features...")

    # Find a sample build
    sample_doc = db["build_samples"].find_one({"tr_original_commit": {"$exists": True}})
    if not sample_doc:
        print("No build sample found. Seeding mock data...")
        from bson import ObjectId
        from datetime import datetime, timezone

        repo_id = ObjectId()
        run_id = 123456

        # Mock Repo
        repo_data = {
            "_id": repo_id,
            "full_name": "octocat/Hello-World",
            "default_branch": "master",
            "source_languages": ["java"],  # Mocking java to trigger some logic
            "main_lang": "java",
            "installation_id": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        db["imported_repositories"].insert_one(repo_data)

        # Mock Workflow Run
        run_data = {
            "workflow_run_id": run_id,
            "repo_id": repo_id,
            "run_number": 1,
            "head_sha": "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d",  # Real SHA from Hello-World
            "status": "completed",
            "conclusion": "success",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "raw_payload": {
                "head_branch": "master",
                "pull_requests": [],
                "event": "push",
            },
        }
        db["workflow_runs_raw"].insert_one(run_data)

        # Mock Build Sample
        sample_data = {
            "repo_id": repo_id,
            "workflow_run_id": run_id,
            "tr_original_commit": "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d",
            "gh_build_started_at": datetime.now(timezone.utc),
            "git_all_built_commits": ["7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"],
        }
        db["build_samples"].insert_one(sample_data)

        sample_doc = db["build_samples"].find_one({"_id": sample_data.get("_id")})
        print("Seeded mock data for octocat/Hello-World")

        # Create dummy log file
        log_dir = Path("../repo-data/job_logs") / str(repo_id) / str(run_id)
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "1.log").write_text(
            "Tests run: 10, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.5 sec"
        )
        print(f"Created dummy log at {log_dir}/1.log")

    build_sample = BuildSample(**sample_doc)
    print(f"Testing with build sample: {build_sample.id}")

    repo_doc = db["imported_repositories"].find_one({"_id": build_sample.repo_id})
    repo = ImportedRepository(**repo_doc)

    run_doc = db["workflow_runs_raw"].find_one(
        {"workflow_run_id": build_sample.workflow_run_id}
    )
    workflow_run = WorkflowRunRaw(**run_doc) if run_doc else None

    context = ExtractionContext(
        build_sample=build_sample, workflow_run=workflow_run, repo=repo, db=db
    )

    # List all registered features
    print(f"Registered features: {len(registry.list_features())}")

    # Test Git Features
    print("\nTesting Git Features:")
    from app.services.features.base import FeatureSource

    known_values = {}

    git_results = registry.extract_source(
        FeatureSource.GIT_HISTORY, context, known_values
    )
    for name, val in git_results.items():
        print(f"  {name}: {val} (Success: {val is not None})")
    known_values.update(git_results)

    # Test Build Log Features
    print("\nTesting Build Log Features:")
    log_results = registry.extract_source(
        FeatureSource.BUILD_LOG, context, known_values
    )
    for name, val in log_results.items():
        print(f"  {name}: {val} (Success: {val is not None})")
    known_values.update(log_results)

    # Test GitHub Discussion Features
    print("\nTesting GitHub Discussion Features:")
    discussion_results = registry.extract_source(
        FeatureSource.GITHUB_API, context, known_values
    )
    for name, val in discussion_results.items():
        print(f"  {name}: {val} (Success: {val is not None})")
    known_values.update(discussion_results)

    # Test Repo Snapshot Features
    print("\nTesting Repo Snapshot Features:")
    snapshot_results = registry.extract_source(
        FeatureSource.REPO_SNAPSHOT, context, known_values
    )
    for name, val in snapshot_results.items():
        print(f"  {name}: {val} (Success: {val is not None})")
    known_values.update(snapshot_results)


if __name__ == "__main__":
    verify_features()
