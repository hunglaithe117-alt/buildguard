"""
Build Log Resource Manager.

Provides shared access to build log files for feature extraction.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.services.extracts.log_parser import TestLogParser, ParsedLog

from ..base import ExtractionContext

logger = logging.getLogger(__name__)

LOG_DIR = Path("../repo-data/job_logs")


class BuildLogResource:
    """
    Manages access to build log files.
    
    Usage:
        resource = BuildLogResource.from_context(context)
        if resource.is_available:
            for log_file, parsed in resource.parsed_logs.items():
                print(f"{log_file}: {parsed.tests_run} tests")
    """
    
    CACHE_KEY = "build_log_resource"
    
    def __init__(
        self,
        log_dir: Path,
        log_files: List[Path],
        parsed_logs: Dict[str, ParsedLog],
    ):
        self.log_dir = log_dir
        self.log_files = log_files
        self.parsed_logs = parsed_logs
    
    @property
    def is_available(self) -> bool:
        """Check if any logs are available."""
        return len(self.log_files) > 0
    
    @property
    def job_ids(self) -> List[int]:
        """Get list of job IDs from log files."""
        return [int(f.stem) for f in self.log_files]
    
    @classmethod
    def from_context(
        cls,
        context: ExtractionContext,
        log_dir: Optional[Path] = None,
    ) -> "BuildLogResource":
        """
        Get or create a BuildLogResource from the extraction context.
        
        Uses caching to avoid redundant parsing.
        """
        # Check cache first
        if context.has_cache(cls.CACHE_KEY):
            cached = context.get_cache(cls.CACHE_KEY)
            if isinstance(cached, BuildLogResource):
                return cached
        
        base_log_dir = log_dir or LOG_DIR
        repo_id = str(context.build_sample.repo_id)
        run_id = str(context.build_sample.workflow_run_id)
        
        run_log_dir = base_log_dir / repo_id / run_id
        
        if not run_log_dir.exists():
            logger.warning(f"No logs found for {repo_id}/{run_id}")
            return cls(run_log_dir, [], {})
        
        log_files = list(run_log_dir.glob("*.log"))
        if not log_files:
            logger.warning(f"No log files found in {run_log_dir}")
            return cls(run_log_dir, [], {})
        
        # Parse all logs
        parser = TestLogParser()
        parsed_logs: Dict[str, ParsedLog] = {}
        
        for log_file in log_files:
            try:
                content = log_file.read_text(errors="replace")
                parsed = parser.parse(content)
                parsed_logs[log_file.stem] = parsed
            except Exception as e:
                logger.error(f"Failed to parse log {log_file}: {e}")
        
        resource = cls(run_log_dir, log_files, parsed_logs)
        context.set_cache(cls.CACHE_KEY, resource)
        return resource
    
    def get_raw_content(self, job_id: int) -> Optional[str]:
        """Get raw log content for a specific job."""
        log_file = self.log_dir / f"{job_id}.log"
        if log_file.exists():
            return log_file.read_text(errors="replace")
        return None
    
    def get_parsed(self, job_id: int) -> Optional[ParsedLog]:
        """Get parsed log for a specific job."""
        return self.parsed_logs.get(str(job_id))
    
    def aggregate_tests_run(self) -> int:
        """Get total tests run across all jobs."""
        return sum(p.tests_run for p in self.parsed_logs.values())
    
    def aggregate_tests_failed(self) -> int:
        """Get total tests failed across all jobs."""
        return sum(p.tests_failed for p in self.parsed_logs.values())
    
    def aggregate_tests_skipped(self) -> int:
        """Get total tests skipped across all jobs."""
        return sum(p.tests_skipped for p in self.parsed_logs.values())
    
    def aggregate_tests_ok(self) -> int:
        """Get total tests passed across all jobs."""
        return sum(p.tests_ok for p in self.parsed_logs.values())
    
    def aggregate_duration(self) -> float:
        """Get total test duration across all jobs."""
        return sum(
            p.test_duration_seconds or 0.0
            for p in self.parsed_logs.values()
        )
    
    def get_frameworks(self) -> List[str]:
        """Get list of unique frameworks detected."""
        frameworks = set()
        for parsed in self.parsed_logs.values():
            if parsed.framework:
                frameworks.add(parsed.framework)
        return list(frameworks)
