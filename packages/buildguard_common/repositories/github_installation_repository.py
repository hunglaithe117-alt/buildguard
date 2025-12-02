"""Repository for GitHub installations (infra layer)."""

from typing import Optional

from buildguard_common.models.github_installation import GithubInstallation
from buildguard_common.repositories.base import BaseRepository, CollectionName


class GithubInstallationRepository(BaseRepository[GithubInstallation]):
    def __init__(self, db):
        super().__init__(db, CollectionName.GITHUB_INSTALLATIONS, GithubInstallation)

    def find_by_installation_id(
        self, installation_id: str
    ) -> Optional[GithubInstallation]:
        return self.find_one({"installation_id": installation_id})


__all__ = ["GithubInstallationRepository"]
