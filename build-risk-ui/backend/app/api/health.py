"""
Health check endpoints
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from pymongo.database import Database

from app.database.mongo import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Simple API health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Build Risk Assessment API",
    }


@router.get("/health/db")
async def database_health(db: Database = Depends(get_db)):
    """MongoDB health check."""
    try:
        db.command("ping")
        status = "healthy"
    except Exception as exc:  # pragma: no cover - best effort probe
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(exc),
            "timestamp": datetime.utcnow().isoformat(),
        }

    return {
        "status": status,
        "database": "connected",
        "timestamp": datetime.utcnow().isoformat(),
    }
