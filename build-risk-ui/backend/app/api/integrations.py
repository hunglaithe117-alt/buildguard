from fastapi import APIRouter, Depends
from pymongo.database import Database

from app.database.mongo import get_db
from app.dtos.github import (
    GithubInstallationListResponse,
    GithubInstallationResponse,
)
from app.middleware.auth import get_current_user
from app.services.integration_service import IntegrationService

router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.get(
    "/github/installations",
    response_model=GithubInstallationListResponse,
    response_model_by_alias=False,
)
def list_github_installations(
    db: Database = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    service = IntegrationService(db)
    return service.list_github_installations()


@router.get(
    "/github/installations/{installation_id}",
    response_model=GithubInstallationResponse,
    response_model_by_alias=False,
)
def get_github_installation(
    installation_id: str,
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = IntegrationService(db)
    return service.get_github_installation(installation_id)


@router.post(
    "/github/sync",
    response_model=GithubInstallationListResponse,
    response_model_by_alias=False,
)
def sync_github_installations(
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Sync GitHub App installations from GitHub API."""
    service = IntegrationService(db)
    return service.sync_installations(current_user["_id"])
