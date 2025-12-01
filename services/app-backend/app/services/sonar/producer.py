"""Compatibility shim: re-export sonar producer from infra."""

from app.infra import sonar_producer, SonarScanProducer  # noqa: F401
