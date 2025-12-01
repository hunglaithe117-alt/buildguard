# Backend Structure (Work-in-Progress)

This repo now shares a consistent layering between services:

- **domain/**: Re-exports entities/DTOs for use across the app. Existing models remain in their original locations, but imports should go through `app.domain.entities` (build-risk) or `app.domain` (scan-commit).
- **infra/**: Gateways to external systems and persistence. GitHub/Sonar/Mongo helpers and repository shims live here. Consumers should import repositories via `app.infra.repositories.*`.
- **services/**: Application logic/use-cases. Should depend on domain/infra, not directly on low-level modules.
- **workers/** (build-risk): Celery-facing orchestration and base task classes.
- **api/**: FastAPI routers/DTOs.

Shared utilities live in `packages/python-common` (logging, Mongo client caching, Celery task base, GitHub client/exceptions).

Refactor status:
- **build-risk**: Domain/infra/workers shims in place; imports updated to go through shims. Repositories still live in `app/repositories` but are consumed via `app.infra.repositories`.
- **scan-commit**: Added infra + domain shims; API/tasks now import the repository aggregate via `app.infra.repositories`. Repositories remain in `app/services/*_repository.py`.

Next steps:
- Optionally move repository modules physically under `app/infra/repositories` (keep compatibility shims).
- Align scan-commit with the full layering (add workers if needed, expand infra for integrations).
- Run `uv sync` at the repo root to pull workspace changes before running services.
