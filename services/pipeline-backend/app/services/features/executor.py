"""
Feature Extraction Executor.

This module orchestrates the extraction of multiple features,
handling dependency resolution and parallel execution where possible.
"""

import logging
from typing import Any, Dict, List, Optional, Set

from pymongo.database import Database

from app.domain.entities import BuildSample, ImportedRepository, WorkflowRunRaw
from app.repositories import ImportedRepositoryRepository, WorkflowRunRepository

from .base import ExtractionContext, FeatureResult, FeatureSource
from .registry import FeatureRegistry, registry as global_registry

logger = logging.getLogger(__name__)


class FeatureExecutor:
    """
    Executes feature extraction with dependency management.
    
    Usage:
        executor = FeatureExecutor(db)
        
        # Extract specific features
        results = executor.extract(
            build_sample=sample,
            features=["tr_log_tests_run_sum", "gh_team_size"]
        )
        
        # Extract all features from a source
        results = executor.extract_by_source(
            build_sample=sample,
            source=FeatureSource.BUILD_LOG
        )
    """
    
    def __init__(
        self,
        db: Optional[Database] = None,
        registry: Optional[FeatureRegistry] = None
    ):
        self.db = db
        self.registry = registry or global_registry
    
    def extract(
        self,
        build_sample: BuildSample,
        features: List[str],
        workflow_run: Optional[WorkflowRunRaw] = None,
        repo: Optional[ImportedRepository] = None,
    ) -> Dict[str, Any]:
        """
        Extract specified features for a build sample.
        
        Args:
            build_sample: The build sample to extract features for.
            features: List of feature names to extract.
            workflow_run: Optional workflow run data.
            repo: Optional repository metadata.
            
        Returns:
            Dict mapping feature names to their values.
        """
        # Resolve context
        workflow_run, repo = self._resolve_context(build_sample, workflow_run, repo)
        
        # Create extraction context
        context = ExtractionContext(
            build_sample=build_sample,
            workflow_run=workflow_run,
            repo=repo,
            db=self.db,
        )
        
        # Resolve dependencies and get execution order
        try:
            ordered_features = self.registry.resolve_dependencies(features)
        except ValueError as e:
            logger.error(f"Dependency resolution failed: {e}")
            return {name: None for name in features}
        
        # Execute features in order
        results: Dict[str, Any] = {}
        
        for feature_name in ordered_features:
            result = self._extract_single(context, feature_name, results)
            results[feature_name] = result.value if result.success else None
            
            if not result.success:
                logger.warning(
                    f"Feature {feature_name} extraction failed: {result.error}"
                )
        
        # Return only requested features (not dependencies)
        return {name: results.get(name) for name in features}
    
    def extract_by_source(
        self,
        build_sample: BuildSample,
        source: FeatureSource,
        workflow_run: Optional[WorkflowRunRaw] = None,
        repo: Optional[ImportedRepository] = None,
    ) -> Dict[str, Any]:
        """
        Extract all features from a specific source.
        
        Args:
            build_sample: The build sample to extract features for.
            source: The feature source to extract from.
            workflow_run: Optional workflow run data.
            repo: Optional repository metadata.
            
        Returns:
            Dict mapping feature names to their values.
        """
        features = list(self.registry.get_by_source(source))
        return self.extract(build_sample, features, workflow_run, repo)
    
    def extract_all(
        self,
        build_sample: BuildSample,
        workflow_run: Optional[WorkflowRunRaw] = None,
        repo: Optional[ImportedRepository] = None,
    ) -> Dict[str, Any]:
        """
        Extract all registered features.
        
        Args:
            build_sample: The build sample to extract features for.
            workflow_run: Optional workflow run data.
            repo: Optional repository metadata.
            
        Returns:
            Dict mapping feature names to their values.
        """
        features = list(self.registry.get_all_names())
        return self.extract(build_sample, features, workflow_run, repo)
    
    def _extract_single(
        self,
        context: ExtractionContext,
        feature_name: str,
        computed: Dict[str, Any],
    ) -> FeatureResult:
        """Extract a single feature."""
        feature_cls = self.registry.get(feature_name)
        
        if not feature_cls:
            return FeatureResult.failure(
                feature_name,
                f"Feature '{feature_name}' not found in registry"
            )
        
        # Gather dependencies
        dependencies = {
            dep: computed.get(dep)
            for dep in feature_cls.dependencies
        }
        
        # Check dependencies
        missing_deps = [
            dep for dep in feature_cls.dependencies
            if dep not in computed
        ]
        if missing_deps:
            return FeatureResult.failure(
                feature_name,
                f"Missing dependencies: {missing_deps}"
            )
        
        try:
            feature = feature_cls(self.db)
            return feature.extract(context, dependencies)
        except Exception as e:
            logger.exception(f"Error extracting {feature_name}")
            return FeatureResult.failure(feature_name, str(e))
    
    def _resolve_context(
        self,
        build_sample: BuildSample,
        workflow_run: Optional[WorkflowRunRaw],
        repo: Optional[ImportedRepository],
    ):
        """Resolve workflow_run and repo from database if missing."""
        resolved_run = workflow_run
        resolved_repo = repo
        
        if not resolved_run and self.db:
            run_repo = WorkflowRunRepository(self.db)
            resolved_run = run_repo.find_by_repo_and_run_id(
                build_sample.repo_id, build_sample.workflow_run_id
            )
            if not resolved_run:
                resolved_run = run_repo.find_one({
                    "repo_id": build_sample.repo_id,
                    "$or": [
                        {"run_id": build_sample.workflow_run_id},
                        {"workflow_run_id": build_sample.workflow_run_id},
                    ],
                })
        
        if not resolved_repo and self.db:
            resolved_repo = ImportedRepositoryRepository(self.db).find_by_id(
                build_sample.repo_id
            )
        
        return resolved_run, resolved_repo
    
    def get_available_features(self) -> List[Dict]:
        """Get list of all available features with metadata."""
        return self.registry.list_features()
    
    def validate_features(self, features: List[str]) -> Dict[str, bool]:
        """
        Validate that the requested features exist.
        
        Returns:
            Dict mapping feature names to their validity.
        """
        all_names = self.registry.get_all_names()
        return {name: name in all_names for name in features}
