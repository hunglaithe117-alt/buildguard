from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Set, Tuple

from pymongo.database import Database

from app.domain.entities import BuildSample, ImportedRepository, WorkflowRunRaw
from app.repositories import ImportedRepositoryRepository, WorkflowRunRepository


class BaseExtractor(ABC):
    """
    Abstract base class for all feature extractors.
    """

    # Identifier for the source type (FeatureSourceType value or custom)
    source: str | None = None
    # Keys produced by this extractor. Used to filter partial requests.
    supported_features: Set[str] = set()

    def __init__(self, db: Optional[Database] = None):
        self.db = db

    @abstractmethod
    def extract(
        self,
        build_sample: BuildSample,
        workflow_run: Optional[WorkflowRunRaw] = None,
        repo: Optional[ImportedRepository] = None,
        selected_features: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Extract features from the given build context.

        Args:
            build_sample: The build sample to extract features for.
            workflow_run: The raw workflow run data (optional, depends on extractor).
            repo: The repository metadata (optional).

        Returns:
            A dictionary of extracted features.
        """
        pass

    def _resolve_context(
        self,
        build_sample: BuildSample,
        workflow_run: Optional[WorkflowRunRaw],
        repo: Optional[ImportedRepository],
    ) -> Tuple[Optional[WorkflowRunRaw], Optional[ImportedRepository]]:
        """
        Resolve workflow_run and repo from the database if missing.
        """
        resolved_run = workflow_run
        resolved_repo = repo

        if not resolved_run and self.db:
            run_repo = WorkflowRunRepository(self.db)
            resolved_run = run_repo.find_by_repo_and_run_id(
                build_sample.repo_id, build_sample.workflow_run_id
            )
            if not resolved_run:
                resolved_run = run_repo.find_one(
                    {
                        "repo_id": build_sample.repo_id,
                        "$or": [
                            {"run_id": build_sample.workflow_run_id},
                            {"workflow_run_id": build_sample.workflow_run_id},
                        ],
                    }
                )

        if not resolved_repo and self.db:
            resolved_repo = ImportedRepositoryRepository(self.db).find_by_id(
                build_sample.repo_id
            )

        return resolved_run, resolved_repo

    def _filter_features(
        self, result: Dict[str, Any], selected_features: Optional[List[str]]
    ) -> Dict[str, Any]:
        if not selected_features:
            return result

        allowed = set(selected_features)
        if self.supported_features:
            allowed = allowed & self.supported_features
        return {k: v for k, v in result.items() if k in allowed}
