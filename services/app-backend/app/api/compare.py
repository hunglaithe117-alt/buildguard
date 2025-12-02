from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database

from app.database.mongo import get_db
from app.middleware.auth import (
    get_current_user,
)
from app.services.diff_service import DiffService

router = APIRouter()


@router.get("/{repo_id}/compare")
def compare_builds(
    repo_id: str,
    base_build_id: str = Query(..., description="ID of the base build"),
    head_build_id: str = Query(..., description="ID of the head build"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Compare two builds to see differences in metrics and files.
    """
    service = DiffService(db)
    try:
        return service.compare_builds(repo_id, base_build_id, head_build_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
