import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from bson import ObjectId

from buildguard_common.models import ImportStatus
from app.repositories import ImportedRepositoryRepository, WorkflowRunRepository
from app.domain.entities import WorkflowRunRaw
from buildguard_common.github_wiring import (
    get_app_github_client,
    get_public_github_client,
)
from app.core.config import settings
from app.core.redis import get_redis
from buildguard_common.tasks import TASK_DOWNLOAD_LOGS
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def get_github_client(db, repo_full_name: str):
    # Check if we have an installation for this repo
    repo_repo = ImportedRepositoryRepository(db)
    repo = repo_repo.find_one({"full_name": repo_full_name})

    if repo and repo.installation_id:
        return get_app_github_client(
            db=db,
            installation_id=repo.installation_id,
            app_id=settings.github.app_id,
            private_key=settings.github.private_key,
            api_url=settings.github.api_url,
            redis_client=get_redis(),
        )
    else:
        # Fallback to public client
        return get_public_github_client(
            tokens=settings.github.tokens, api_url=settings.github.api_url
        )


def ensure_repository_exists(db, user_id: ObjectId, full_name: str) -> str:
    repo_repo = ImportedRepositoryRepository(db)
    repo = repo_repo.find_one({"full_name": full_name, "user_id": user_id})
    if not repo:
        # Create a stub repository
        repo_doc = repo_repo.upsert_repository(
            query={"full_name": full_name, "user_id": user_id},
            data={
                "provider": "github",
                "default_branch": "main",  # Will be updated later if needed
                "import_status": ImportStatus.IMPORTED.value,
                "ci_provider": "github_actions",
            },
        )
        return str(repo_doc.id)
    return str(repo.id)


def process_workflow_run(
    db, repo_id: str, run: Dict[str, Any], trigger_logs: bool = True
) -> bool:
    """
    Process a single workflow run: create/update DB record and trigger log download.
    Returns True if a new run was inserted, False otherwise.
    """
    workflow_run_repo = WorkflowRunRepository(db)
    run_id = run.get("id")

    workflow_run = WorkflowRunRaw(
        repo_id=ObjectId(repo_id),
        workflow_run_id=run_id,
        head_sha=run.get("head_sha"),
        run_number=run.get("run_number"),
        status=run.get("status"),
        conclusion=run.get("conclusion"),
        created_at=datetime.fromisoformat(run.get("created_at").replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(run.get("updated_at").replace("Z", "+00:00")),
        raw_payload=run,
        log_fetched=False,
    )

    existing = workflow_run_repo.find_by_repo_and_run_id(repo_id, run_id)
    if not existing:
        workflow_run_repo.insert_one(workflow_run)

        if trigger_logs:
            celery_app.send_task(TASK_DOWNLOAD_LOGS, args=[repo_id, run_id])

        return True
    else:
        # Update existing if needed
        if (
            existing.status != workflow_run.status
            or existing.conclusion != workflow_run.conclusion
        ):
            workflow_run_repo.update_one(
                str(existing.id),
                {
                    "status": workflow_run.status,
                    "conclusion": workflow_run.conclusion,
                    "updated_at": workflow_run.updated_at,
                },
            )
        return False
