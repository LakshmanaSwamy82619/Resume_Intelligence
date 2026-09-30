from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_hr
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.config import get_settings
from app.db.session import get_db
from app.models.candidate import Candidate
from app.models.search import Search
from app.models.shortlist import RecruiterShortlist, RecruiterShortlistCandidate
from app.models.user import User
from app.schemas.shortlist import (
    ShortlistCandidateAddRequest,
    ShortlistCandidateUpdateRequest,
    ShortlistCreateRequest,
    ShortlistUpdateRequest,
)
from app.services.profile_completeness import profile_completeness
from app.services.email_service import candidate_stage_email, send_email
from app.services.notification_service import record_audit_log

router = APIRouter(prefix="/api/v1/shortlists", tags=["shortlists"])
settings = get_settings()


async def _get_shortlist(db: AsyncSession, shortlist_id: str, owner_id: str) -> RecruiterShortlist:
    stmt = (
        select(RecruiterShortlist)
        .where(RecruiterShortlist.id == shortlist_id, RecruiterShortlist.owner_user_id == owner_id)
        .options(selectinload(RecruiterShortlist.candidates))
    )
    shortlist = (await db.execute(stmt)).scalar_one_or_none()
    if not shortlist:
        raise NotFoundError("Shortlist not found.")
    return shortlist


async def _serialize(db: AsyncSession, shortlist: RecruiterShortlist) -> dict:
    candidate_ids = [entry.candidate_id for entry in shortlist.candidates]
    candidates = {}
    if candidate_ids:
        rows = (await db.execute(
            select(Candidate)
            .where(Candidate.id.in_(candidate_ids))
            .options(
                selectinload(Candidate.experience), selectinload(Candidate.projects),
                selectinload(Candidate.education), selectinload(Candidate.certifications),
            )
        )).scalars().unique().all()
        candidates = {candidate.id: candidate for candidate in rows}
    return {
        "id": shortlist.id,
        "name": shortlist.name,
        "search_id": shortlist.search_id,
        "email_cc": settings.BOOTSTRAP_ADMIN_EMAIL,
        "created_at": shortlist.created_at,
        "updated_at": shortlist.updated_at,
        "candidates": [
            {
                "candidate_id": entry.candidate_id,
                "full_name": candidates[entry.candidate_id].full_name if entry.candidate_id in candidates else None,
                "email": candidates[entry.candidate_id].email if entry.candidate_id in candidates else None,
                "years_of_experience": candidates[entry.candidate_id].years_of_experience if entry.candidate_id in candidates else None,
                "technical_skills": candidates[entry.candidate_id].technical_skills if entry.candidate_id in candidates else [],
                "profile_completeness": profile_completeness(candidates[entry.candidate_id]) if entry.candidate_id in candidates else None,
                "source_search_id": entry.source_search_id,
                "stage": entry.stage,
                "notes": entry.notes,
                "added_at": entry.created_at,
            }
            for entry in shortlist.candidates
        ],
    }


async def _validate_source_search(db: AsyncSession, search_id: str | None, owner_id: str, candidate_ids: list[str]) -> None:
    if not search_id:
        return
    search = (await db.execute(
        select(Search).where(Search.id == search_id, Search.hr_user_id == owner_id).options(selectinload(Search.candidates))
    )).scalar_one_or_none()
    if not search:
        raise NotFoundError("Search not found.")
    allowed = {entry.candidate_id for entry in search.candidates}
    if any(candidate_id not in allowed for candidate_id in candidate_ids):
        raise ValidationAppError("Every selected candidate must belong to the chosen search results.")


async def _validate_candidates(db: AsyncSession, candidate_ids: list[str]) -> None:
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValidationAppError("Candidate IDs must be unique.")
    existing = set((await db.execute(select(Candidate.id).where(Candidate.id.in_(candidate_ids)))).scalars().all()) if candidate_ids else set()
    if existing != set(candidate_ids):
        raise NotFoundError("One or more candidates were not found.")


@router.get("")
async def list_shortlists(user: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(RecruiterShortlist)
        .where(RecruiterShortlist.owner_user_id == user.id)
        .options(selectinload(RecruiterShortlist.candidates))
        .order_by(RecruiterShortlist.updated_at.desc())
    )).scalars().unique().all()
    return [await _serialize(db, row) for row in rows]


@router.post("")
async def create_shortlist(payload: ShortlistCreateRequest, user: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise ValidationAppError("Shortlist name cannot be empty.")
    await _validate_candidates(db, payload.candidate_ids)
    await _validate_source_search(db, payload.search_id, user.id, payload.candidate_ids)
    shortlist = RecruiterShortlist(owner_user_id=user.id, name=name, search_id=payload.search_id)
    db.add(shortlist)
    await db.flush()
    for candidate_id in payload.candidate_ids:
        db.add(RecruiterShortlistCandidate(shortlist_id=shortlist.id, candidate_id=candidate_id, source_search_id=payload.search_id))
    await db.commit()
    await record_audit_log(db, user.id, "shortlist_created", resource_type="shortlist", resource_id=shortlist.id, details={"candidate_count": len(payload.candidate_ids)})
    return await _serialize(db, await _get_shortlist(db, shortlist.id, user.id))


@router.get("/{shortlist_id}")
async def get_shortlist(shortlist_id: str, user: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    return await _serialize(db, await _get_shortlist(db, shortlist_id, user.id))


@router.patch("/{shortlist_id}")
async def rename_shortlist(shortlist_id: str, payload: ShortlistUpdateRequest, user: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    shortlist = await _get_shortlist(db, shortlist_id, user.id)
    name = payload.name.strip()
    if not name:
        raise ValidationAppError("Shortlist name cannot be empty.")
    shortlist.name = name
    await db.commit()
    await record_audit_log(db, user.id, "shortlist_renamed", resource_type="shortlist", resource_id=shortlist.id)
    return await _serialize(db, await _get_shortlist(db, shortlist.id, user.id))


@router.delete("/{shortlist_id}", status_code=204)
async def delete_shortlist(shortlist_id: str, user: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    shortlist = await _get_shortlist(db, shortlist_id, user.id)
    await db.delete(shortlist)
    await record_audit_log(db, user.id, "shortlist_deleted", resource_type="shortlist", resource_id=shortlist_id)
    await db.commit()
    return Response(status_code=204)


@router.post("/{shortlist_id}/candidates")
async def add_candidates(shortlist_id: str, payload: ShortlistCandidateAddRequest, user: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    shortlist = await _get_shortlist(db, shortlist_id, user.id)
    await _validate_candidates(db, payload.candidate_ids)
    await _validate_source_search(db, payload.search_id, user.id, payload.candidate_ids)
    existing = {entry.candidate_id for entry in shortlist.candidates}
    for candidate_id in payload.candidate_ids:
        if candidate_id not in existing:
            db.add(RecruiterShortlistCandidate(shortlist_id=shortlist.id, candidate_id=candidate_id, source_search_id=payload.search_id))
    if payload.search_id and not shortlist.search_id:
        shortlist.search_id = payload.search_id
    await db.commit()
    await record_audit_log(db, user.id, "shortlist_candidates_added", resource_type="shortlist", resource_id=shortlist.id, details={"candidate_count": len(payload.candidate_ids)})
    return await _serialize(db, await _get_shortlist(db, shortlist.id, user.id))


@router.patch("/{shortlist_id}/candidates/{candidate_id}")
async def update_shortlist_candidate(
    shortlist_id: str,
    candidate_id: str,
    payload: ShortlistCandidateUpdateRequest,
    user: User = Depends(require_hr),
    db: AsyncSession = Depends(get_db),
):
    shortlist = await _get_shortlist(db, shortlist_id, user.id)
    entry = next((item for item in shortlist.candidates if item.candidate_id == candidate_id), None)
    if not entry:
        raise NotFoundError("Candidate is not in this shortlist.")
    changes = payload.model_dump(exclude_unset=True)
    if "stage" in changes:
        entry.stage = changes["stage"]
    if "notes" in changes:
        entry.notes = changes["notes"].strip() or None if changes["notes"] is not None else None
    await db.commit()
    await record_audit_log(db, user.id, "shortlist_candidate_updated", resource_type="candidate", resource_id=candidate_id, details={"shortlist_id": shortlist.id, "stage": entry.stage, "notes_updated": "notes" in changes})
    return await _serialize(db, await _get_shortlist(db, shortlist.id, user.id))


@router.post("/{shortlist_id}/candidates/{candidate_id}/email")
async def email_shortlist_candidate(
    shortlist_id: str,
    candidate_id: str,
    user: User = Depends(require_hr),
    db: AsyncSession = Depends(get_db),
):
    shortlist = await _get_shortlist(db, shortlist_id, user.id)
    entry = next((item for item in shortlist.candidates if item.candidate_id == candidate_id), None)
    if not entry:
        raise NotFoundError("Candidate is not in this shortlist.")
    stage = entry.stage
    if stage == "interview":
        stage = "accepted"  # Keep previously saved stages usable with the updated templates.
    if stage not in {"screening", "accepted", "offer", "hired", "rejected"}:
        raise ValidationAppError("Set a recruiting stage before sending email.")
    candidate = await db.get(Candidate, candidate_id)
    if not candidate or not candidate.email:
        raise ValidationAppError("This candidate does not have an email address on their resume.")
    subject, body = candidate_stage_email(candidate.full_name or "there", stage)
    try:
        sent = await asyncio.to_thread(
            send_email,
            candidate.email,
            subject,
            body,
            settings.BOOTSTRAP_ADMIN_EMAIL,
        )
    except Exception as exc:
        await record_audit_log(db, user.id, "candidate_email_failed", resource_type="candidate", resource_id=candidate_id, details={"shortlist_id": shortlist.id, "stage": stage, "error_type": type(exc).__name__})
        raise ValidationAppError("The email could not be sent. Check the email service configuration and try again.") from exc
    if not sent:
        await record_audit_log(db, user.id, "candidate_email_failed", resource_type="candidate", resource_id=candidate_id, details={"shortlist_id": shortlist.id, "stage": stage})
        raise ValidationAppError("The email could not be sent. Check the email service configuration and try again.")
    await record_audit_log(db, user.id, "candidate_email_sent", resource_type="candidate", resource_id=candidate_id, details={"shortlist_id": shortlist.id, "stage": stage, "cc_admin": True})
    return {"sent": True, "recipient": candidate.email, "cc": settings.BOOTSTRAP_ADMIN_EMAIL, "stage": stage}


@router.delete("/{shortlist_id}/candidates/{candidate_id}", status_code=204)
async def remove_candidate(shortlist_id: str, candidate_id: str, user: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    shortlist = await _get_shortlist(db, shortlist_id, user.id)
    entry = next((item for item in shortlist.candidates if item.candidate_id == candidate_id), None)
    if not entry:
        raise NotFoundError("Candidate is not in this shortlist.")
    await db.delete(entry)
    await db.commit()
    await record_audit_log(db, user.id, "shortlist_candidate_removed", resource_type="candidate", resource_id=candidate_id, details={"shortlist_id": shortlist.id})
    return Response(status_code=204)
