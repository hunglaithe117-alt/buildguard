# BuildGuard Refactor Blueprint

This repository hosts two products:
- `build-risk/`: FastAPI + Celery backend, Next.js frontend for build risk assessment (GitHub, SonarQube, heuristics).
- `scan-commit/`: FastAPI + Celery pipeline plus Next.js frontend for TravisTorrent commit ingestion + SonarQube enrichment.
- Shared infra via root `docker-compose.yml` (Mongo, RabbitMQ, Redis, SonarQube, Zipkin).

## Current Structure (high level)
- **Backends**: Both use FastAPI, Celery, Mongo, but diverge on configuration (`env` vs YAML), logging setup, and HTTP client helpers. `build-risk` bundles integrations, pipelines, and heuristics under `app/services`; tasks live under `app/tasks`. `scan-commit` has a leaner layout (`app/api`, `app/services`, `app/tasks`) with YAML-driven settings.
- **Frontends**: Two separate Next.js apps with duplicated UI primitives and API helpers.
- **Ops/Infra**: Docker compose wires both stacks to the same infra. No shared dev tooling scripts for lint/test/build across apps; `uv` workspace ties the two Python backends only.

## Pain Points
- Inconsistent configuration and logging: `build-risk` reads env vars via `app.config.Settings`, while `scan-commit` reads YAML via `app.core.config`; tracing/logging setup differs.
- No shared client libraries: GitHub, SonarQube, Mongo helpers, and task instrumentation are duplicated between the two backends.
- Flattened service layer: `build-risk` mixes routing, services, pipelines, heuristics, and integrations in a single `app/services` package; domain models, DTOs, and repository abstractions are weakly separated.
- Task orchestration scattered: Celery tasks, heuristics, and notifications live alongside HTTP services with minimal boundaries; retry/error policies are not centralized.
- Frontend duplication: UI components, API client patterns, and types are repeated across two Next.js apps; environment variable naming is inconsistent (`NEXT_PUBLIC_API_URL` vs `NEXT_PUBLIC_API_BASE_URL`).

## Target Structure (proposed)
- **Monorepo layout**
  - `apps/build-risk/{backend,frontend}`
  - `apps/scan-commit/{backend,frontend}`
  - `packages/python-common`: shared settings, logging, HTTP clients (GitHub, SonarQube), Mongo helpers, Celery base task mixins, error types.
  - `packages/web-common`: shared UI kit, hooks, API client wrappers, typography/theme tokens.
  - `docs/`: architecture, runbooks, ADRs.
- **Backend layering (both apps)**
  - `core/`: settings, logging, tracing, http clients, dependencies.
  - `domain/`: entities/models, DTOs, value objects.
  - `infra/`: persistence (repositories), external integrations (GitHub, SonarQube, S3), messaging.
  - `services/`: application use-cases (repo import, feature extraction, risk evaluation, scan orchestration).
  - `api/`: routers, request/response schemas, dependency wiring.
  - `workers/`: Celery tasks grouped by concern; orchestration modules own chords/chains/retry policy.
- **Configuration**
  - Standardize on Pydantic settings with `.env` + YAML overlay support; single logging/tracing initializer.
  - Align env var names between apps and compose files; default to shared infra hostnames.
- **Frontends**
  - Shared UI primitives + chart configs in `packages/web-common`.
  - Consistent API client (fetch/axios) with typed responses and common auth handling.
  - Aligned envs: `NEXT_PUBLIC_API_URL` for build-risk, `NEXT_PUBLIC_PIPELINE_API_URL` (or similar) for scan-commit, documented in `.env.example`.

## Step-by-Step Refactor Plan
1) **Foundation**: Add shared python package skeleton (`packages/python-common`) with unified settings/logging/http client helpers; wire both backends to use it without behavior change. Document new layout and env conventions.
2) **Build-Risk backend**: Restructure into `core/domain/infra/services/api/workers`; move Celery task base classes and pipeline orchestrator under `workers`, isolate GitHub/Sonar integrations under `infra`, and clean DTO vs entity usage. Route repository imports through `app.infra.repositories` (shims in place). Next: move entities/DTOs under `app/domain`, migrate remaining integrations, then retire direct `app.repositories` imports.
3) **Scan-Commit backend**: Align structure with the same layering; replace local helpers with shared package; standardize config, logging, and task base classes.
4) **Frontends**: Extract shared UI + hooks into `packages/web-common`; harmonize API clients and env vars; update both apps to consume the shared package.
5) **DX/Ops**: Add root `Makefile`/`justfile` for lint/test/build across apps, and CI workflows to run lint+tests per package. Update `docker-compose.yml` envs to match new settings.

Each step is intended to be incremental and backward-compatible; we can pause after any step with a working system.
