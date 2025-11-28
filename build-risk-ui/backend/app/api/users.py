"""User management helper endpoints (role definitions, login)."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from pymongo.database import Database

from app.database.mongo import get_db
from app.dtos import UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/",
    response_model=List[UserResponse],
    response_model_by_alias=False,
)
def list_users(db: Database = Depends(get_db)):
    service = UserService(db)
    return service.list_users()


@router.get(
    "/me",
    response_model=UserResponse,
    response_model_by_alias=False,
)
def get_current_user(db: Database = Depends(get_db)):
    service = UserService(db)
    return service.get_current_user()
