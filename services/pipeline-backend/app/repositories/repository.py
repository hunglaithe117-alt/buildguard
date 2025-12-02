"""Aggregate repository helper (infra layer)."""

from app.infra.repositories.projects_repository import ProjectsRepository
from app.infra.repositories.scan_jobs_repository import ScanJobsRepository
from app.infra.repositories.scan_results_repository import ScanResultsRepository
from app.infra.repositories.failed_commits_repository import FailedCommitsRepository
from app.infra.repositories.build_samples_repository import BuildSamplesRepository
from app.infra.repositories.workflow_run import WorkflowRunRepository


class Repository:
    def __init__(self) -> None:
        self.projects = ProjectsRepository()
        self.scan_jobs = ScanJobsRepository()
        self.scan_results = ScanResultsRepository()
        self.failed_commits = FailedCommitsRepository()
        self.build_samples = BuildSamplesRepository()
        self.workflow_runs = WorkflowRunRepository()

    # Proxy methods
    def __getattr__(self, name):
        for repo in (
            self.projects,
            self.scan_jobs,
            self.scan_results,
            self.failed_commits,
            self.build_samples,
            self.workflow_runs,
        ):
            if hasattr(repo, name):
                return getattr(repo, name)
        raise AttributeError(name)


repository = Repository()

__all__ = ["Repository", "repository"]
