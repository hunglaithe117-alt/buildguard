"""Domain entities shim layer."""

from buildguard_common.models.build_sample import BuildSample
from buildguard_common.models.imported_repository import (
    ImportedRepository,
    ImportStatus,
)
from buildguard_common.models.workflow_run import WorkflowRunRaw
from buildguard_common.models.oauth_identity import OAuthIdentity
from buildguard_common.models.scan_job import ScanJob, ScanJobStatus
from buildguard_common.models.scan_result import ScanResult
from buildguard_common.models.failed_scan import FailedScan as FailedCommit

# Aliases for legacy/pipeline context
Project = ImportedRepository
ProjectStatus = ImportStatus

# Local models (if not in common yet)
# None left for now
from buildguard_common.models.sonar_config import SonarConfig

__all__ = [
    "BuildSample",
    "ImportedRepository",
    "ImportStatus",
    "WorkflowRunRaw",
    "OAuthIdentity",
    "ScanJob",
    "ScanJobStatus",
    "ScanResult",
    "FailedCommit",
    "Project",
    "ProjectStatus",
    "SonarConfig",
]
