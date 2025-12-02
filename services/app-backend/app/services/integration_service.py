from bson.objectid import ObjectId
from datetime import datetime
from typing import List

from fastapi import HTTPException, status
from pymongo.database import Database
from pymongo import UpdateOne

from app.dtos.github import (
    GithubInstallationListResponse,
    GithubInstallationResponse,
)
from buildguard_common.github_wiring import get_user_github_client


class IntegrationService:
    def __init__(self, db: Database):
        self.db = db

    def list_github_installations(self) -> GithubInstallationListResponse:
        """List all GitHub App installations."""
        installations_cursor = self.db.github_installations.find().sort(
            "installed_at", -1
        )
        installations = [
            GithubInstallationResponse(**inst) for inst in installations_cursor
        ]
        return GithubInstallationListResponse(installations=installations)

    def get_github_installation(
        self, installation_id: str
    ) -> GithubInstallationResponse:
        """Get details of a specific GitHub App installation."""
        installation = self.db.github_installations.find_one(
            {"installation_id": installation_id}
        )
        if not installation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation {installation_id} not found",
            )
        return GithubInstallationResponse(**installation)

    def sync_installations(self, user_id: str) -> GithubInstallationListResponse:
        # Get user's GitHub identity
        client = get_user_github_client(
            db=self.db, user_id=user_id, api_url=settings.GITHUB_API_URL
        )

        if not client:
            return GithubInstallationListResponse(installations=[])

        # Query installations for this account
        installations_cursor = self.db.github_installations.find(
            {"account_login": github_login}
        ).sort("installed_at", -1)

        installations = [
            GithubInstallationResponse(**inst) for inst in installations_cursor
        ]

        return GithubInstallationListResponse(installations=installations)
