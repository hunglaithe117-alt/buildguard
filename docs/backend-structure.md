# BuildGuard monorepo layout (refactored)

- `services/app-backend/`: Build Risk API + Celery workers (was `build-risk/backend`).
- `services/app-frontend/`: Build Risk Next.js UI (was `build-risk/frontend`).
- `services/pipeline-backend/`: Sonar/commit ingestion pipeline API + workers (was `scan-commit/backend`).
- `services/repo-data/`: Local caches/artifacts used by the app-backend defaults.
- `services/sonar_metrics.yml`: Sonar measures list, mounted into the app backend/worker.
- `config/`: Shared configs (`pipeline.yml`, `.env.pipeline.example`, `.env.docker.example`).
- `packages/python-common/`: Shared Python helpers (`buildguard_common`).

Notes:
- `docker-compose.yml` now points at `services/*` contexts and mounts `config/pipeline.yml`.
- The legacy `pipeline-frontend` service is removed; the Build Risk UI already embeds the pipeline views.
- Pipeline config: edit `config/pipeline.yml` (ignored by git) or set `PIPELINE_CONFIG`.
- Sonar metrics: override via `SONAR_METRICS_PATH` or edit `services/sonar_metrics.yml`.
