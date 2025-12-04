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
    git_features = registry.get_by_source("git_history")
    for name in git_features:
        feature_cls = registry.get(name)
        if feature_cls:
            extractor = feature_cls(db)
            try:
                # Setup group if needed
                # In a real executor, we would group by group and call setup
                # Here we just hack it for verification
                if name in registry._groups["git_group"].features:
                    group = registry.get_group("git_group")(db)
                    if not context.has_cache("repo_path"):
                        print("Setting up Git Group...")
                        group.setup(context)

                result = extractor.extract(context, {})
                print(f"  {name}: {result.value} (Success: {result.success})")
            except Exception as e:
                print(f"  {name}: FAILED ({e})")

    # Test Build Log Features
    print("\nTesting Build Log Features:")
    log_features = registry.get_by_source("build_log")
    for name in log_features:
        feature_cls = registry.get(name)
        if feature_cls:
            extractor = feature_cls(db)
            try:
                if name in registry._groups["build_log_group"].features:
                    group = registry.get_group("build_log_group")(db)
                    if not context.has_cache("log_files"):
                        print("Setting up Build Log Group...")
                        group.setup(context)

                result = extractor.extract(context, {})
                print(f"  {name}: {result.value} (Success: {result.success})")
            except Exception as e:
                print(f"  {name}: FAILED ({e})")

    # Test GitHub Discussion Features
    print("\nTesting GitHub Discussion Features:")
    discussion_features = registry.get_by_source("github_api")
    for name in discussion_features:
        feature_cls = registry.get(name)
        if feature_cls:
            extractor = feature_cls(db)
            try:
                # No specific setup needed for discussion group currently
                result = extractor.extract(context, {})
                print(f"  {name}: {result.value} (Success: {result.success})")
            except Exception as e:
                print(f"  {name}: FAILED ({e})")

    # Test Repo Snapshot Features
    print("\nTesting Repo Snapshot Features:")
    snapshot_features = registry.get_by_source("repo_snapshot")
    for name in snapshot_features:
        feature_cls = registry.get(name)
        if feature_cls:
            extractor = feature_cls(db)
            try:
                if name in registry._groups["repo_snapshot_group"].features:
                    group = registry.get_group("repo_snapshot_group")(db)
                    # Reuse repo path if available, or setup will handle it
                    if not context.has_cache("repo_path"):
                        print("Setting up Repo Snapshot Group...")
                        group.setup(context)

                result = extractor.extract(context, {})
                print(f"  {name}: {result.value} (Success: {result.success})")
            except Exception as e:
                print(f"  {name}: FAILED ({e})")


if __name__ == "__main__":
    verify_features()
