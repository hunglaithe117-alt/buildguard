"""
Base classes for the modular feature extraction system.

This module provides the foundation for individual feature extractors,
allowing each feature to be computed independently while managing dependencies.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type, TYPE_CHECKING

from pymongo.database import Database

if TYPE_CHECKING:
    from app.domain.entities import BuildSample, ImportedRepository, WorkflowRunRaw

from buildguard_common.models.features import FeatureDataType


class FeatureSource(str, Enum):
    """Source types for feature extraction."""

    BUILD_LOG = "build_log"
    GIT_HISTORY = "git_history"
    REPO_SNAPSHOT = "repo_snapshot"
    GITHUB_API = "github_api"
    COMPUTED = "computed"  # For features derived from other features


@dataclass
class ExtractionContext:
    """
    Shared context for feature extraction.
    Contains all resources needed by feature extractors.
    """

    build_sample: "BuildSample"
    workflow_run: Optional["WorkflowRunRaw"] = None
    repo: Optional["ImportedRepository"] = None
    db: Optional[Database] = None

    # Cached resources (populated lazily)
    _cache: Dict[str, Any] = field(default_factory=dict)

    def get_cache(self, key: str) -> Optional[Any]:
        """Get a cached value."""
        return self._cache.get(key)

    def set_cache(self, key: str, value: Any) -> None:
        """Set a cached value."""
        self._cache[key] = value

    def has_cache(self, key: str) -> bool:
        """Check if a cache key exists."""
        return key in self._cache


@dataclass
class FeatureResult:
    """Result of a single feature extraction."""

    name: str
    value: Any
    success: bool = True
    error: Optional[str] = None

    @classmethod
    def failure(cls, name: str, error: str) -> "FeatureResult":
        return cls(name=name, value=None, success=False, error=error)


class BaseFeature(ABC):
    """
    Abstract base class for individual feature extractors.

    Each feature should inherit from this class and implement:
    - name: The feature identifier
    - source: The data source required
    - dependencies: Other features this feature depends on
    - extract(): The extraction logic
    """

    # Feature identifier (e.g., "tr_log_tests_run_sum")
    name: str = ""

    # Data source required for this feature
    source: FeatureSource = FeatureSource.COMPUTED

    # Data type of the feature value
    data_type: FeatureDataType = FeatureDataType.STRING

    # Set of feature names this feature depends on
    dependencies: Set[str] = set()

    # Description for documentation
    description: str = ""

    def __init__(self, db: Optional[Database] = None):
        self.db = db

    @abstractmethod
    def extract(
        self, context: ExtractionContext, dependencies: Dict[str, Any]
    ) -> FeatureResult:
        """
        Extract the feature value.

        Args:
            context: The extraction context with all resources.
            dependencies: Dict of dependency feature names to their values.

        Returns:
            FeatureResult with the extracted value.
        """
        pass

    def validate_dependencies(self, dependencies: Dict[str, Any]) -> bool:
        """Check if all required dependencies are present."""
        return all(dep in dependencies for dep in self.dependencies)


class FeatureGroup(ABC):
    """
    A group of related features that share common resources.

    Use this when multiple features need the same expensive setup
    (e.g., cloning a repo, parsing logs).
    """

    # Group identifier
    name: str = ""

    # Source type for all features in this group
    source: FeatureSource = FeatureSource.COMPUTED

    # Features provided by this group
    features: Set[str] = set()

    def __init__(self, db: Optional[Database] = None):
        self.db = db

    @abstractmethod
    def setup(self, context: ExtractionContext) -> bool:
        """
        Perform any setup required before extraction.
        Returns True if setup succeeded.
        """
        pass

    @abstractmethod
    def extract_all(
        self, context: ExtractionContext, selected_features: Optional[Set[str]] = None
    ) -> Dict[str, FeatureResult]:
        """
        Extract all features (or selected subset) from this group.

        Args:
            context: The extraction context.
            selected_features: Optional set of feature names to extract.
                             If None, extract all features.

        Returns:
            Dict mapping feature names to their results.
        """
        pass

    def teardown(self, context: ExtractionContext) -> None:
        """Clean up any resources after extraction."""
        pass


# Type alias for feature registry
FeatureRegistry = Dict[str, Type[BaseFeature]]


def get_dependency_order(features: List[str], registry: FeatureRegistry) -> List[str]:
    """
    Topologically sort features based on their dependencies.

    Args:
        features: List of feature names to sort.
        registry: Registry of feature classes.

    Returns:
        List of feature names in dependency order.
    """
    # Build dependency graph
    graph: Dict[str, Set[str]] = {}
    for name in features:
        if name in registry:
            feature_cls = registry[name]
            graph[name] = feature_cls.dependencies & set(features)
        else:
            graph[name] = set()

    # Kahn's algorithm for topological sort
    in_degree = {name: 0 for name in features}
    for name, deps in graph.items():
        for dep in deps:
            if dep in in_degree:
                in_degree[name] += 1

    queue = [name for name, degree in in_degree.items() if degree == 0]
    result = []

    while queue:
        node = queue.pop(0)
        result.append(node)

        for name, deps in graph.items():
            if node in deps:
                in_degree[name] -= 1
                if in_degree[name] == 0 and name not in result:
                    queue.append(name)

    # Check for cycles
    if len(result) != len(features):
        missing = set(features) - set(result)
        raise ValueError(f"Circular dependency detected involving: {missing}")

    return result
