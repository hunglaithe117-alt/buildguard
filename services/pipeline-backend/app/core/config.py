"""Centralised configuration loader for the pipeline services."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

import yaml
from pydantic import BaseModel, Field


class PathsSettings(BaseModel):
    uploads: Path = Field(default=Path("/app/data/uploads"))
    exports: Path = Field(default=Path("/app/data/exports"))
    default_workdir: Path = Field(default=Path("/app/data/sonar-work"))


class MongoSettings(BaseModel):
    uri: str = Field(default="mongodb://travis:travis@mongo:27017")
    database: str = Field(default="travistorrent_pipeline")
    options: Dict[str, Any] = Field(default_factory=lambda: {"authSource": "admin"})


class BrokerSettings(BaseModel):
    url: str = Field(default="amqp://pipeline:pipeline@rabbitmq:5672//")
    result_backend: str = Field(default="rpc://")
    default_queue: str = Field(default="pipeline.default")


class PipelineTuning(BaseModel):
    ingestion_chunk_size: int = Field(default=2000)
    default_retry_limit: int = Field(default=3)
    csv_encoding: str = Field(default="utf-8")


class SonarMeasures(BaseModel):
    keys: list[str] = Field(default_factory=list)
    chunk_size: int = Field(default=25)
    output_format: str = Field(default="csv")


class SonarInstanceSettings(BaseModel):
    name: str
    host: str
    token: Optional[str] = Field(default=None)

    def resolved_token(self) -> str:
        if self.token:
            return self.token
        raise RuntimeError(
            f"SonarQube token missing for instance '{self.name}'. " "Configure `token`."
        )


class SonarSettings(BaseModel):
    webhook_secret: str = Field(default="change-me")
    webhook_public_url: str = Field(default="http://localhost:8000/api/sonar/webhook")
    measures: SonarMeasures = Field(default_factory=SonarMeasures)
    instances: List[SonarInstanceSettings] = Field(default_factory=list)

    def get_instances(self) -> List[SonarInstanceSettings]:
        return self.instances

    def get_instance(self, name: Optional[str] = None) -> SonarInstanceSettings:
        instances = self.get_instances()
        if name:
            for instance in instances:
                if instance.name == name:
                    return instance
            raise ValueError(f"Sonar instance '{name}' is not configured.")
        return instances[0]


class StorageCollections(BaseModel):
    projects_collection: str = Field(default="imported_repositories")
    scan_jobs_collection: str = Field(default="scan_jobs")
    scan_results_collection: str = Field(default="scan_results")
    failed_commits_collection: str = Field(default="failed_commits")
    build_samples_collection: str = Field(default="build_samples")


class WebSettings(BaseModel):
    base_url: str = Field(default="http://localhost:3000")


class LoggingSettings(BaseModel):
    """Logging configuration loaded from pipeline.yml."""

    # Accept either a level name (e.g. INFO, DEBUG) or numeric level as str.
    level: str = Field(default="INFO")


class S3Settings(BaseModel):
    """S3 configuration for storing logs."""

    enabled: bool = Field(default=False)
    bucket_name: str = Field(default="")
    region: str = Field(default="us-east-1")
    access_key_id: Optional[str] = Field(default=None)
    secret_access_key: Optional[str] = Field(default=None)
    endpoint_url: Optional[str] = Field(default=None)
    sonar_logs_prefix: str = Field(default="sonar-logs")
    error_logs_prefix: str = Field(default="error-logs")


class GitHubSettings(BaseModel):
    api_url: str = Field(default="https://api.github.com")
    tokens: List[str] = Field(default_factory=list)
    max_parent_hops: int = Field(default=50)
    app_id: Optional[str] = Field(default=None)
    private_key: Optional[str] = Field(default=None)
    client_id: Optional[str] = Field(default=None)
    client_secret: Optional[str] = Field(default=None)


class NotificationSettings(BaseModel):
    slack_webhook_url: Optional[str] = Field(default=None)


class RedisSettings(BaseModel):
    url: str = Field(default="redis://redis:6379/0")


class Settings(BaseModel):
    environment: str = Field(default="local")
    paths: PathsSettings = Field(default_factory=PathsSettings)
    mongo: MongoSettings = Field(default_factory=MongoSettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    pipeline: PipelineTuning = Field(default_factory=PipelineTuning)
    sonarqube: SonarSettings = Field(default_factory=SonarSettings)
    storage: StorageCollections = Field(default_factory=StorageCollections)
    web: WebSettings = Field(default_factory=WebSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    s3: S3Settings = Field(default_factory=S3Settings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)

    @property
    def sonar_token(self) -> str:
        instance = self.sonarqube.get_instance()
        return instance.resolved_token()


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Config at {path} must be a mapping")
        return data


def _config_path() -> Path:
    env_path = os.getenv("PIPELINE_CONFIG")
    if env_path:
        return Path(env_path).expanduser().resolve()
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "config" / "pipeline.yml"
        if candidate.exists():
            return candidate
    return current.parents[3] / "config" / "pipeline.yml"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    raw = _load_yaml(_config_path())

    if raw.get("paths") and not os.path.exists("/app"):
        for key in ["uploads", "exports", "default_workdir"]:
            val = raw["paths"].get(key)
            if val and str(val).startswith("/app"):
                raw["paths"][key] = str(val).replace("/app", str(Path.cwd()))

    return Settings(**raw)


settings = get_settings()
