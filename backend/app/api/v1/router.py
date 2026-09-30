from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, auth, candidates, evaluation, health, hr, jobs, notifications, profile, resumes, search, shortlists

api_router = APIRouter()
# Keep the root health URLs for container probes and expose the same checks
# under the versioned API prefix used by the frontend.
api_router.include_router(health.router)
api_router.include_router(health.router, prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(hr.router)
api_router.include_router(resumes.router)
api_router.include_router(candidates.router)
api_router.include_router(jobs.router)
api_router.include_router(search.router)
api_router.include_router(shortlists.router)
api_router.include_router(evaluation.router)
api_router.include_router(notifications.router)
api_router.include_router(profile.router)
