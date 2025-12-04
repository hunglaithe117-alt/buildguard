"""GitHub installation entity - tracks GitHub App installations"""

from datetime import datetime
from typing import Optional

from .base import BaseEntity


class GithubInstallation(BaseEntity):
    installation_id: str
    account_login: Optional[str] = None
    account_type: Optional[str] = None  # "User" or "Organization"
    installed_at: datetime
    revoked_at: Optional[datetime] = None
    uninstalled_at: Optional[datetime] = None
    suspended_at: Optional[datetime] = None
