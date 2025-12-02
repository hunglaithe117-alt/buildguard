from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from app.database.mongo import get_db
from app.repositories import BuildSampleRepository, ImportedRepositoryRepository

router = APIRouter()


@router.get("/check")
def check_gate(
    repo_id: str = Query(..., description="Repository ID"),
    commit_sha: str = Query(..., description="Commit SHA"),
    db: Database = Depends(get_db),
) -> Dict[str, Any]:
    """
    Deployment Gate API.
    Checks if a build is safe to deploy based on risk analysis.
    """
    build_repo = BuildSampleRepository(db)
    # Find build by repo_id and commit_sha
    # We assume tr_original_commit matches commit_sha
    # Since find_by_repo_and_run_id uses run_id, we need a new method or find_one

    # We can use find_one with query
    build = build_repo.collection.find_one(
        {
            "repo_id": build_repo._ensure_object_id(repo_id),
            "tr_original_commit": commit_sha,
        }
    )

    if not build:
        return {
            "allowed": False,
            "reason": "Build analysis not found or pending",
            "risk_factors": [],
        }

    # Convert to object to access fields easily if needed, or just use dict
    # build is a dict from pymongo

    status = build.get("status")
    if status != "completed":
        return {
            "allowed": False,
            "reason": f"Build analysis status is {status}",
            "risk_factors": [],
        }

    risk_factors = build.get("risk_factors", [])

    # Check Shadow Mode
    repo_repo = ImportedRepositoryRepository(db)
    repo = repo_repo.find_by_id(repo_id)
    if repo and repo.shadow_mode:
        return {
            "allowed": True,
            "reason": f"Shadow Mode enabled (Risk Factors: {len(risk_factors)})",
            "risk_factors": risk_factors,
        }

    if risk_factors:
        return {
            "allowed": False,
            "reason": "High risk detected",
            "risk_factors": risk_factors,
        }

    return {"allowed": True, "reason": "No risks detected", "risk_factors": []}
