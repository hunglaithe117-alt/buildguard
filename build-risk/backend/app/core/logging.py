import logging
import sys
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings after parsing the LogRecord.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return str(log_record)


def setup_logging():
    """
    Setup structured logging for the application.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    # handler.setFormatter(JSONFormatter()) # Use JSON for production/Alloy parsing

    # For now, keep simple formatting for development readability,
    # but ensure it goes to stdout so Docker/Alloy picks it up.
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    # Set lower level for some noisy libraries if needed
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
