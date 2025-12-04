from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from pymongo.database import Database
from pydantic import BaseModel, Field

from app.database.mongo import get_db
from app.middleware.auth import get_current_user
from app.services.dataset_service import DatasetService
from buildguard_common.models.dataset_template import DatasetTemplate
from buildguard_common.models.dataset import DatasetConfig, DatasetSource

router = APIRouter(prefix="/datasets", tags=["Datasets"])


class CreateDatasetRequest(BaseModel):
    name: str
    description: Optional[str] = None
    source_type: DatasetSource
    config: DatasetConfig
    template_id: Optional[str] = None


class CsvPreviewResponse(BaseModel):
    headers: List[str]
    sample_rows: List[Dict[str, Any]]
    total_rows_estimate: int


def get_service(db: Database = Depends(get_db)) -> DatasetService:
    return DatasetService(db)


@router.get("/templates/all", response_model=List[Any])
async def list_templates(
    service: DatasetService = Depends(get_service),
    current_user: dict = Depends(get_current_user),
):
    """Get list of available dataset templates."""
    return await service.get_all_templates()


@router.post("/preview-csv", response_model=CsvPreviewResponse)
async def preview_csv(
    file: UploadFile = File(...),
    service: DatasetService = Depends(get_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Parse uploaded CSV and return headers + sample rows.
    Does NOT save the file permanently yet.
    """
    try:
        return await service.preview_csv_upload(file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("", status_code=201)
async def create_dataset(
    payload: CreateDatasetRequest,
    service: DatasetService = Depends(get_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new dataset configuration.
    """
    try:
        dataset_id = await service.create_dataset(payload)
        return {"id": str(dataset_id), "message": "Dataset created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
