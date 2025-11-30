from celery import chain, chord
from app.tasks.extractors import (
    extract_build_log_features,
    extract_repo_snapshot_features,
    extract_git_features,
    extract_github_discussion_features,
    finalize_build_sample
)

class PipelineOrchestrator:
    def run_pipeline(self, build_id: str):
        """
        Orchestrates the feature extraction pipeline for a given build.
        Uses Celery chord to run independent extractors in parallel,
        and chains dependent ones (Git -> Discussion).
        """
        # Fan-out tasks
        header = [
            extract_build_log_features.s(build_id),
            extract_repo_snapshot_features.s(build_id),
            chain(
                extract_git_features.si(build_id),
                extract_github_discussion_features.si(build_id),
            ),
        ]

        callback = finalize_build_sample.s(build_id)

        # Execute
        chord(header)(callback)
