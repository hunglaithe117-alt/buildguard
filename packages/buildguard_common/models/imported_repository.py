"""Repository entity - represents a tracked repository"""

from typing import Optional
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List
from pydantic import Field

from .base import BaseEntity, PyObjectId


class Provider(str, Enum):

    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"


class TestFramework(str, Enum):

    PYTEST = "pytest"
    UNITTEST = "unittest"
    RSPEC = "rspec"
    MINITEST = "minitest"
    TESTUNIT = "testunit"
    CUCUMBER = "cucumber"
    JUNIT = "junit"
    TESTNG = "testng"


class SourceLanguage(str, Enum):

    PYTHON = "python"
    RUBY = "ruby"
    JAVA = "java"


class CIProvider(str, Enum):

    GITHUB_ACTIONS = "github_actions"
    TRAVIS_CI = "travis_ci"


class ImportStatus(str, Enum):

    QUEUED = "queued"
    IMPORTING = "importing"
    IMPORTED = "imported"
    FAILED = "failed"


class ImportedRepository(BaseEntity):
    user_id: Optional[PyObjectId] = None
    provider: Provider = Provider.GITHUB

    full_name: str  # "owner/repo"
    github_repo_id: Optional[int] = None
    default_branch: Optional[str] = None
    is_private: bool = False
    main_lang: Optional[str] = None

    test_frameworks: List[TestFramework] = []
    source_languages: List[SourceLanguage] = []

    ci_provider: CIProvider = CIProvider.GITHUB_ACTIONS
    installation_id: Optional[str] = None

    import_status: ImportStatus = ImportStatus.QUEUED
    total_builds_imported: int = 0
    last_scanned_at: Optional[datetime] = None
    last_sync_error: Optional[str] = None
    notes: Optional[str] = None

    # Lazy Sync Fields
    last_synced_at: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = {}

    # Risk Governance
    risk_thresholds: Dict[str, int] = {"high": 80, "medium": 50}
    shadow_mode: bool = False
    auto_sonar_scan: bool = False
