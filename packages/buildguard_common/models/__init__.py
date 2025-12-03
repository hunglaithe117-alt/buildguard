"""Database entity models - represents the actual structure stored in MongoDB"""

from .base import BaseEntity, PyObjectId
from .build_sample import BuildSample
from .workflow_run import WorkflowRunRaw
from .github_installation import GithubInstallation
from .oauth_identity import OAuthIdentity
from .scan_job import ScanJob, ScanJobStatus
from .failed_scan import FailedScan, ScanStatus
from .imported_repository import (
    ImportedRepository,
    Provider,
    TestFramework,
    SourceLanguage,
    CIProvider,
    ImportStatus,
)
from .sonar_config import SonarConfig
from .user import User
from .feature import FeatureDefinition, FeatureDataType, FeatureSourceType
from .dataset_template import DatasetTemplate
from .dataset import TrainingDataset, DatasetStatus, FieldMapping

__all__ = [
    "BaseEntity",
    "PyObjectId",
    "GithubInstallation",
    "OAuthIdentity",
    "ImportedRepository",
    "User",
    "SonarConfig",
    # Enums
    "Provider",
    "TestFramework",
    "SourceLanguage",
    "CIProvider",
    "ImportStatus",
    "BuildSample",
    "WorkflowRunRaw",
    "ScanJob",
    "ScanJobStatus",
    "FailedScan",
    "ScanStatus",
    "FeatureDefinition",
    "FeatureDataType",
    "FeatureSourceType",
    "DatasetTemplate",
    "TrainingDataset",
    "DatasetStatus",
    "FieldMapping",
]
