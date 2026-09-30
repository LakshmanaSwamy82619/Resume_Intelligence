from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(tags=["health"])
settings = get_settings()


async def _check_db(db: AsyncSession) -> bool:
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_redis() -> bool:
    try:
        import redis

        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        return bool(client.ping())
    except Exception:
        return False


def _check_celery() -> bool:
    """Return true when a worker answers the broker's ping request."""
    try:
        from app.workers.celery_app import celery_app

        replies = celery_app.control.inspect(timeout=1.0).ping()
        return bool(replies)
    except Exception:
        return False


@router.get("/health")
async def health():
    return {"status": "ok", "service": settings.APP_NAME}


@router.get("/health/live")
async def liveness():
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    db_ok = await _check_db(db)
    redis_ok = _check_redis()
    celery_ok = _check_celery() if redis_ok else False
    ready = db_ok and redis_ok and celery_ok
    return {
        "status": "ready" if ready else "not_ready",
        "database": "ok" if db_ok else "unavailable",
        "redis": "ok" if redis_ok else "unavailable",
        "celery": "ok" if celery_ok else "unavailable",
    }
