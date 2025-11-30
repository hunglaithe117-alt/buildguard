import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger
from opentelemetry import trace

class OTelJSONFormatter(jsonlogger.JsonFormatter):
    """
    JSON Formatter that injects OpenTelemetry trace_id and span_id.
    """
    def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        
        # Inject OTel context
        span = trace.get_current_span()
        if span != trace.NonRecordingSpan(None):
            ctx = span.get_span_context()
            if ctx.is_valid:
                log_record["trace_id"] = trace.format_trace_id(ctx.trace_id)
                log_record["span_id"] = trace.format_span_id(ctx.span_id)
        
        # Ensure level is uppercase
        if "level" in log_record:
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname


def setup_logging(level: str = "INFO") -> None:
    """
    Configure root logger to output JSON to stdout.
    """
    handler = logging.StreamHandler(sys.stdout)
    formatter = OTelJSONFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"}
    )
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    
    # Remove existing handlers to avoid duplicates
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
        
    root_logger.addHandler(handler)
    
    # Silence noisy libraries
    logging.getLogger("uvicorn.access").disabled = True  # We might want to keep this or format it too
    logging.getLogger("urllib3").setLevel("WARNING")
