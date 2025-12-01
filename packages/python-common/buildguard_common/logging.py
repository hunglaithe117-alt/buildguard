"""Logging helpers shared across BuildGuard services."""

from __future__ import annotations

import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger
from opentelemetry import trace


class OTelJSONFormatter(jsonlogger.JsonFormatter):
    """
    JSON formatter that injects OpenTelemetry trace/span identifiers.
    """

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        span = trace.get_current_span()
        if span != trace.NonRecordingSpan(None):
            ctx = span.get_span_context()
            if ctx.is_valid:
                log_record["trace_id"] = trace.format_trace_id(ctx.trace_id)
                log_record["span_id"] = trace.format_span_id(ctx.span_id)

        # Normalize level casing
        if "level" in log_record:
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname


def setup_logging(level: str = "INFO") -> None:
    """
    Configure root logger to emit JSON logs with OTel correlation.
    """
    handler = logging.StreamHandler(sys.stdout)
    formatter = OTelJSONFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Remove existing handlers to avoid duplicate logs when reloading
    for existing in root_logger.handlers[:]:
        root_logger.removeHandler(existing)

    root_logger.addHandler(handler)

    # Silence noisy libraries
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("urllib3").setLevel("WARNING")
