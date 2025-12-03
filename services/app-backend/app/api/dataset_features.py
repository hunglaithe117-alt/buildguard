from typing import List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Body
from pymongo.database import Database
from pydantic import BaseModel
from bson import ObjectId

from app.database.mongo import get_db
from app.middleware.auth import get_current_user
from app.services.dataset_builder_service import DatasetBuilderService
from buildguard_common.models.dataset_import_job import DatasetImportJob

router = APIRouter(prefix="/datasets", tags=["Dataset Features"])


class StartExtractionRequest(BaseModel):
    selected_features: List[str]
    extractor_config: Dict[str, Any] = {}


def get_service(db: Database = Depends(get_db)) -> DatasetBuilderService:
    return DatasetBuilderService(db)


@router.get("/{job_id}/features", response_model=List[Dict[str, Any]])
async def get_job_features(
    job_id: str,
    service: DatasetBuilderService = Depends(get_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Get available features for a job based on its template.
    Returns a list of feature definitions.
    """
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.dataset_template_id:
        raise HTTPException(status_code=400, detail="Job has no template assigned")

    # Fetch template and its features
    # We need to extend DatasetBuilderService to support this or do it here.
    # Ideally, service should handle logic.
    return await service.get_features_for_job(job_id)


@router.post("/{job_id}/start-extraction")
async def start_extraction(
    job_id: str,
    payload: StartExtractionRequest,
    service: DatasetBuilderService = Depends(get_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Update job with selected features and trigger extraction tasks.
    """
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        await service.start_extraction(
            job_id, payload.selected_features, payload.extractor_config
        )
        return {"status": "success", "message": "Extraction started"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
