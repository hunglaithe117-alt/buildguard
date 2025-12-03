from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from app.domain.entities import BuildSample, ImportedRepository, WorkflowRunRaw


class BaseExtractor(ABC):
    """
    Abstract base class for all feature extractors.
    """

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
