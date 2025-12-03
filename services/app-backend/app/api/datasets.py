from typing import List
from fastapi import APIRouter, Depends, HTTPException, Body
from pymongo.database import Database
from pydantic import BaseModel

from app.database.mongo import get_db
from app.middleware.auth import get_current_user
from app.services.dataset_service import DatasetService
from buildguard_common.models.dataset_template import DatasetTemplate

router = APIRouter(prefix="/datasets", tags=["Datasets"])


class AnalyzeRequest(BaseModel):
    dataset_id: str  # ID của dataset sau khi upload file
    template_id: str


def get_service(db: Database = Depends(get_db)) -> DatasetService:
    return DatasetService(db)


@router.get("/templates/all", response_model=List[DatasetTemplate])
async def list_templates(
    service: DatasetService = Depends(get_service),
    current_user: dict = Depends(get_current_user),
):
    """Lấy danh sách các mẫu (TravisTorrent, Custom...)"""
    return await service.get_all_templates()


@router.post("/analyze-mapping")
async def analyze_mapping(
    payload: AnalyzeRequest,
    service: DatasetService = Depends(get_service),
    current_user: dict = Depends(get_current_user),
):
    """
    API quan trọng: Frontend gọi API này sau khi user chọn Template.
    Backend sẽ đọc file CSV đã upload của dataset_id và trả về bảng mapping gợi ý.
    """
    dataset = await service.get_dataset(payload.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    try:
        # Gọi hàm logic ở service vừa viết
        result = await service.analyze_csv_mapping(
            dataset["raw_file_path"], payload.template_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
