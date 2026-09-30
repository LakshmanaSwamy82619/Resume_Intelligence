from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.LOG_LEVEL)

    # Dev/test convenience: auto-create tables when running against SQLite.
    # Production (Postgres) should use `alembic upgrade head` instead
    # (see alembic/ and README "Database setup").
    if settings.DATABASE_URL.startswith("sqlite"):
        from app.db.session import init_models

        await init_models()

    await _bootstrap_admin_if_configured()

    yield


async def _bootstrap_admin_if_configured() -> None:
    """One-time convenience: if BOOTSTRAP_ADMIN_EMAIL/PASSWORD are set and no
    admin user exists yet, create one. This solves the "who creates the
    first Admin" bootstrap problem (Admin creates HR, but nothing creates
    the first Admin) without a hard-coded default credential in code.
    """
    if not settings.BOOTSTRAP_ADMIN_EMAIL or not settings.BOOTSTRAP_ADMIN_PASSWORD:
        return

    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.session import AsyncSessionLocal
    from app.models.enums import UserRole
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        existing_admin = (await db.execute(select(User).where(User.role == UserRole.ADMIN.value))).scalars().first()
        if existing_admin:
            return
        admin = User(
            email=settings.BOOTSTRAP_ADMIN_EMAIL.lower(),
            hashed_password=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
            full_name="System Administrator",
            role=UserRole.ADMIN.value,
            is_active=True,
        )
        db.add(admin)
        await db.commit()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI-Powered Resume Intelligence & Candidate Matching",
        description="Hybrid retrieval + reranking + multi-agent candidate matching backend.",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)

    return app


app = create_app()
