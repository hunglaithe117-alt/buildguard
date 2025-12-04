from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    status,
    HTTPException,
    File,
    UploadFile,
    Form,
)
from pymongo.database import Database

from app.database.mongo import get_db
from app.dtos.ingestion import IngestionJobResponse
from app.middleware.auth import get_current_user
from app.services.dataset_builder_service import DatasetBuilderService

router = APIRouter(prefix="/dataset-builder", tags=["Dataset Builder"])


@router.post(
    "/jobs",
    response_model=IngestionJobResponse,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_import_job(
    source_type: str = Form(...),
    repo_url: Optional[str] = Form(None),
    dataset_template_id: Optional[str] = Form(None),
    max_builds: int = Form(100),
    selected_features: Optional[List[str]] = Form(None),
    csv_file: Optional[UploadFile] = File(None),
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new dataset import job (GitHub or CSV)."""
    user_id = str(current_user["_id"])
    service = DatasetBuilderService(db)

    if source_type == "github" and not repo_url:
        raise HTTPException(
            status_code=400, detail="repo_url is required for GitHub ingestion"
        )

    if source_type == "csv" and not csv_file:
        raise HTTPException(
            status_code=400, detail="csv_file is required for CSV ingestion"
        )

    # Construct payload object or pass args.
    # We'll modify service.create_job to accept args or we can construct a dict/object.
    # Let's pass the raw args to the service to handle the file stream.
    return await service.create_job(
        user_id=user_id,
        source_type=source_type,
        repo_url=repo_url,
        dataset_template_id=dataset_template_id,
        max_builds=max_builds,
        selected_features=selected_features,
        csv_file=csv_file,
    )


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


@router.get(
    "/features",
    response_model=List[dict],
)
def list_available_features(
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all available features for custom dataset creation."""
    service = DatasetBuilderService(db)
    return service.list_available_features()
