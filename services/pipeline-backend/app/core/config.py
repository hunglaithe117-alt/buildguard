"""Centralised configuration loader for the pipeline services."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field
from buildguard_common.repositories.base import CollectionName

# Auto-load .env in this service directory (similar to app-backend behavior)
def _load_env_file():
    # Skip when running in Docker or explicitly disabled
    if os.getenv("PIPELINE_SKIP_DOTENV") == "1" or Path("/.dockerenv").exists():
        return
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
    except Exception:
        # If loading fails, continue with existing environment
        pass


_load_env_file()


class PathsSettings(BaseModel):
    uploads: Path = Field(default=Path("/app/data/uploads"))
    exports: Path = Field(default=Path("/app/data/exports"))
    default_workdir: Path = Field(default=Path("/app/data/sonar-work"))


class MongoSettings(BaseModel):
    uri: str = Field(
        default_factory=lambda: os.getenv(
            "MONGODB_URI", "mongodb://travis:travis@mongo:27017"
        )
    )
    database: str = Field(default="travistorrent_pipeline")
    options: Dict[str, Any] = Field(default_factory=lambda: {"authSource": "admin"})


class BrokerSettings(BaseModel):
    url: str = Field(
        default_factory=lambda: os.getenv(
            "CELERY_BROKER_URL", "amqp://pipeline:pipeline@rabbitmq:5672//"
        )
    )
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


class SonarSettings(BaseModel):
    webhook_secret: str = Field(
        default_factory=lambda: os.getenv("SONAR_WEBHOOK_SECRET", "change-me")
    )
    webhook_public_url: str = Field(
        default_factory=lambda: os.getenv(
            "SONAR_WEBHOOK_PUBLIC_URL", "http://localhost:8000/api/sonar/webhook"
        )
    )
    host: str = Field(
        default_factory=lambda: os.getenv("SONAR_HOST_URL", "http://localhost:9000")
    )
    token: Optional[str] = Field(default=None)
    measures: SonarMeasures = Field(default_factory=SonarMeasures)

    def resolved_token(self) -> str:
        if self.token:
            return self.token

        # Fallback to env var if token is not in config
        env_token = os.getenv("SONAR_TOKEN")
        if env_token:
            return env_token

        raise RuntimeError("SonarQube token missing. Configure `token`.")

    # Compatibility methods for single instance
    def get_instance(self, name: Optional[str] = None) -> "SonarSettings":
        # Return self as the single instance, ignoring name
        # We add a 'name' property dynamically to mimic the old object if needed,
        # but better to just return self and let caller handle it.
        # However, the caller expects an object with .name, .host, .resolved_token()
        # Let's just return self, and ensure self has those.
        return self

    @property
    def name(self) -> str:
        return "primary"


class StorageCollections(BaseModel):
    projects_collection: str = Field(default=CollectionName.REPOSITORIES.value)
    scan_jobs_collection: str = Field(default=CollectionName.SCAN_JOBS.value)
    scan_results_collection: str = Field(default=CollectionName.SCAN_RESULTS.value)
    failed_commits_collection: str = Field(default=CollectionName.FAILED_COMMITS.value)
    build_samples_collection: str = Field(default=CollectionName.BUILD_SAMPLES.value)


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
    tokens: List[str] = Field(
        default_factory=lambda: (
            os.getenv("GITHUB_TOKENS", "").split(",")
            if os.getenv("GITHUB_TOKENS")
            else []
        )
    )
    max_parent_hops: int = Field(default=50)
    app_id: Optional[str] = Field(default=None)
    private_key: Optional[str] = Field(default=None)
    client_id: Optional[str] = Field(default=None)
    client_secret: Optional[str] = Field(default=None)


class NotificationSettings(BaseModel):
    slack_webhook_url: Optional[str] = Field(default=None)


class RedisSettings(BaseModel):
    url: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://redis:6379/0")
    )


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
        return self.sonarqube.resolved_token()


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
