from typing import List

from fastapi import APIRouter, Depends, Path, Query, status, HTTPException
from pymongo.database import Database

from app.database.mongo import get_db
from app.dtos.ingestion import IngestionJobCreateRequest, IngestionJobResponse
from app.middleware.auth import get_current_user
from app.services.dataset_builder_service import DatasetBuilderService

router = APIRouter(prefix="/dataset-builder", tags=["Dataset Builder"])


@router.post(
    "/jobs",
    response_model=IngestionJobResponse,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
def create_import_job(
    payload: IngestionJobCreateRequest,
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new dataset import job (GitHub or CSV)."""
    user_id = str(current_user["_id"])
    service = DatasetBuilderService(db)

    if payload.source_type == "github" and not payload.repo_url:
        raise HTTPException(
            status_code=400, detail="repo_url is required for GitHub ingestion"
        )

    if payload.source_type == "csv" and not payload.csv_content:
        if not payload.csv_content:
            raise HTTPException(
                status_code=400, detail="csv_content is required for CSV ingestion"
            )

    return service.create_job(user_id, payload)


@router.get(
    "/jobs",
    response_model=List[IngestionJobResponse],
    response_model_by_alias=False,
)
def list_import_jobs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List dataset import jobs."""
    user_id = str(current_user["_id"])
    service = DatasetBuilderService(db)
    return service.list_jobs(user_id, skip, limit)


@router.get(
    "/jobs/{job_id}",
    response_model=IngestionJobResponse,
    response_model_by_alias=False,
)
def get_import_job(
    job_id: str = Path(..., description="Job ID"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get dataset import job details."""
    service = DatasetBuilderService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
