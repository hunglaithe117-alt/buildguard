"""
Feature Registry - Central registry for all available features.

This module provides:
1. Registration of individual feature extractors
2. Discovery of available features
3. Dependency resolution
"""

from typing import Dict, List, Optional, Set, Type

from .base import BaseFeature, FeatureGroup, FeatureSource

from .base import BaseFeature, FeatureGroup, FeatureSource


class FeatureRegistry:
    """
    Central registry for all feature extractors.

    Usage:
        registry = FeatureRegistry()
        registry.register(MyFeature)

        # Get all features for a source
        features = registry.get_by_source(FeatureSource.BUILD_LOG)

        # Get feature by name
        feature_cls = registry.get("tr_log_tests_run_sum")
    """

    _instance: Optional["FeatureRegistry"] = None

    def __new__(cls) -> "FeatureRegistry":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._features: Dict[str, Type[BaseFeature]] = {}
            cls._instance._groups: Dict[str, Type[FeatureGroup]] = {}
            cls._instance._source_map: Dict[FeatureSource, Set[str]] = {
                source: set() for source in FeatureSource
            }
        return cls._instance

    def register(self, feature_cls: Type[BaseFeature]) -> None:
        """Register a feature extractor class."""
        if not feature_cls.name:
            raise ValueError(f"Feature class {feature_cls.__name__} must have a name")

        self._features[feature_cls.name] = feature_cls
        self._source_map[feature_cls.source].add(feature_cls.name)

    def register_group(self, group_cls: Type[FeatureGroup]) -> None:
        """Register a feature group class."""
        if not group_cls.name:
            raise ValueError(f"Group class {group_cls.__name__} must have a name")

        self._groups[group_cls.name] = group_cls
        for feature_name in group_cls.features:
            self._source_map[group_cls.source].add(feature_name)

    def get(self, name: str) -> Optional[Type[BaseFeature]]:
        """Get a feature class by name."""
        return self._features.get(name)

    def get_group(self, name: str) -> Optional[Type[FeatureGroup]]:
        """Get a feature group class by name."""
        return self._groups.get(name)

    def get_by_source(self, source: FeatureSource) -> Set[str]:
        """Get all feature names for a given source."""
        return self._source_map.get(source, set())

    def get_all_names(self) -> Set[str]:
        """Get all registered feature names."""
        all_names = set(self._features.keys())
        for group_cls in self._groups.values():
            all_names.update(group_cls.features)
        return all_names

    def get_dependencies(self, name: str) -> Set[str]:
        """Get dependencies for a feature."""
        feature_cls = self._features.get(name)
        if feature_cls:
            return feature_cls.dependencies
        return set()

    def resolve_dependencies(self, features: List[str]) -> List[str]:
        """
        Resolve all dependencies and return features in execution order.

        Args:
            features: List of requested feature names.

        Returns:
            List of feature names including dependencies, in topological order.
        """
        # Collect all required features including dependencies
        required = set(features)
        to_process = list(features)

        while to_process:
            current = to_process.pop()
            deps = self.get_dependencies(current)
            for dep in deps:
                if dep not in required:
                    required.add(dep)
                    to_process.append(dep)

        # Topological sort
        return self._topological_sort(list(required))

    def _topological_sort(self, features: List[str]) -> List[str]:
        """Sort features by dependencies (Kahn's algorithm)."""
        # Build in-degree map
        in_degree: Dict[str, int] = {name: 0 for name in features}

        for name in features:
            deps = self.get_dependencies(name)
            for dep in deps:
                if dep in in_degree:
                    in_degree[name] += 1

        # Start with features that have no dependencies
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            # Reduce in-degree for dependent features
            for name in features:
                if node in self.get_dependencies(name):
                    in_degree[name] -= 1
                    if in_degree[name] == 0 and name not in result:
                        queue.append(name)

        if len(result) != len(features):
            missing = set(features) - set(result)
            raise ValueError(f"Circular dependency detected: {missing}")

        return result

    def list_features(self) -> List[Dict]:
        """List all features with metadata."""
        result = []

        for name, cls in self._features.items():
            result.append(
                {
                    "name": name,
                    "source": cls.source.value,
                    "dependencies": list(cls.dependencies),
                    "description": cls.description,
                }
            )

        # Add features from groups
        for group_name, group_cls in self._groups.items():
            for feature_name in group_cls.features:
                if feature_name not in self._features:
                    result.append(
                        {
                            "name": feature_name,
                            "source": group_cls.source.value,
                            "group": group_name,
                            "dependencies": [],
                            "description": "",
                        }
                    )

        return sorted(result, key=lambda x: x["name"])

    def clear(self) -> None:
        """Clear all registrations (useful for testing)."""
        self._features.clear()
        self._groups.clear()
        for source in FeatureSource:
            self._source_map[source] = set()


# Global registry instance
registry = FeatureRegistry()


def register_feature(cls: Type[BaseFeature]) -> Type[BaseFeature]:
    """Decorator to register a feature class."""
    registry.register(cls)
    return cls


def register_group(cls: Type[FeatureGroup]) -> Type[FeatureGroup]:
    """Decorator to register a feature group class."""
    registry.register_group(cls)
    return cls


# Import definitions to ensure registration
# noinspection PyUnresolvedReferences
import app.services.features.definitions.git

# noinspection PyUnresolvedReferences
import app.services.features.definitions.build_log

# noinspection PyUnresolvedReferences
import app.services.features.definitions.github_discussion

# noinspection PyUnresolvedReferences
import app.services.features.definitions.repo_snapshot
