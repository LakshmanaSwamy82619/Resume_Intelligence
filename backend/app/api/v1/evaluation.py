from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_admin, require_hr
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.db.session import get_db
from app.evaluation.dataset import add_label, add_query, create_dataset, get_dataset_with_queries
from app.evaluation.runner import run_evaluation
from app.models.enums import UserRole
from app.models.user import Notification, User
from app.models.search import EvaluationDataset, EvaluationLabel, EvaluationQuery, EvaluationRequest, EvaluationResult
from app.models.candidate import Candidate
from app.schemas.evaluation import (
    EvaluationDatasetCreateRequest,
    EvaluationLabelCreateRequest,
    EvaluationQueryCreateRequest,
    EvaluationRunRequest,
    EvaluationMetricsSummaryResponse,
    EvaluationRequestCreateRequest,
    EvaluationSubmissionRunRequest,
)
from app.services.notification_service import record_audit_log

router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])


@router.post("/datasets")
async def create_evaluation_dataset(payload: EvaluationDatasetCreateRequest, user: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    dataset = await create_dataset(db, payload.name, payload.description, user.id)
    await record_audit_log(db, user.id, "evaluation_dataset_created", resource_type="evaluation_dataset", resource_id=dataset.id)
    return {"id": dataset.id, "name": dataset.name}


@router.post("/datasets/{dataset_id}/queries")
async def add_evaluation_query(dataset_id: str, payload: EvaluationQueryCreateRequest, user: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    dataset = await db.get(EvaluationDataset, dataset_id)
    if not dataset or dataset.created_by_user_id != user.id:
        raise NotFoundError("Evaluation dataset not found.")
    query = await add_query(db, dataset_id, payload.query_text)
    await record_audit_log(db, user.id, "evaluation_query_added", resource_type="evaluation_query", resource_id=query.id, details={"dataset_id": dataset_id})
    return {"id": query.id, "query_text": query.query_text}


@router.post("/queries/{query_id}/labels")
async def add_evaluation_label(query_id: str, payload: EvaluationLabelCreateRequest, user: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    query = (
        await db.execute(
            select(EvaluationQuery)
            .where(EvaluationQuery.id == query_id)
            .options(selectinload(EvaluationQuery.dataset))
        )
    ).scalar_one_or_none()
    if not query or query.dataset.created_by_user_id != user.id:
        raise NotFoundError("Evaluation query not found.")
    if not await db.get(Candidate, payload.candidate_id):
        raise NotFoundError("Candidate not found.")
    label = await add_label(db, query_id, payload.candidate_id, payload.relevance, user.id, payload.skill_statuses)
    await record_audit_log(db, user.id, "evaluation_candidate_labeled", resource_type="evaluation_label", resource_id=label.id, details={"query_id": query_id, "relevance": payload.relevance})
    return {"id": label.id}


@router.get("/datasets/{dataset_id}")
async def get_dataset(dataset_id: str, user: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    dataset = await get_dataset_with_queries(db, dataset_id)
    if not dataset or dataset.created_by_user_id != user.id:
        raise NotFoundError("Evaluation dataset not found.")
    latest_request = (
        await db.execute(
            select(EvaluationRequest)
            .where(EvaluationRequest.dataset_id == dataset_id, EvaluationRequest.requested_by_user_id == user.id)
            .order_by(EvaluationRequest.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    result = await db.get(EvaluationResult, latest_request.evaluation_result_id) if latest_request and latest_request.evaluation_result_id else None
    return {
        "id": dataset.id,
        "name": dataset.name,
        "queries": [
            {"id": q.id, "query_text": q.query_text, "labels": [{"candidate_id": l.candidate_id, "relevance": l.relevance, "skill_statuses": l.skill_statuses or {}} for l in q.labels]}
            for q in dataset.queries
        ],
        "evaluation_request": ({
            "id": latest_request.id,
            "status": latest_request.status,
            "top_n": latest_request.top_n,
            "created_at": latest_request.created_at,
            "completed_at": latest_request.completed_at,
            "metrics": result.metrics if result else None,
            "notes": result.notes if result else None,
        } if latest_request else None),
    }


@router.post("/datasets/{dataset_id}/requests")
async def request_dataset_evaluation(dataset_id: str, payload: EvaluationRequestCreateRequest, user: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    dataset = await db.get(EvaluationDataset, dataset_id)
    if not dataset or dataset.created_by_user_id != user.id:
        raise NotFoundError("Evaluation dataset not found.")

    labels_count = (await db.execute(
        select(func.count(EvaluationLabel.id))
        .join(EvaluationQuery, EvaluationQuery.id == EvaluationLabel.query_id)
        .where(EvaluationQuery.dataset_id == dataset_id)
    )).scalar_one()
    if labels_count == 0:
        raise ValidationAppError("Add at least one human relevance label before requesting an evaluation.")

    pending = (await db.execute(
        select(EvaluationRequest).where(EvaluationRequest.dataset_id == dataset_id, EvaluationRequest.status.in_(["pending", "running"]))
    )).scalar_one_or_none()
    if pending:
        return {"id": pending.id, "dataset_id": dataset_id, "status": pending.status, "top_n": pending.top_n, "created_at": pending.created_at}

    request = EvaluationRequest(dataset_id=dataset_id, requested_by_user_id=user.id, top_n=payload.top_n, status="pending")
    db.add(request)
    await db.flush()
    admins = (await db.execute(select(User).where(User.role == UserRole.ADMIN.value, User.is_active.is_(True)))).scalars().all()
    for admin in admins:
        db.add(Notification(
            user_id=admin.id,
            notification_type="evaluation_request",
            title="Evaluation run requested",
            message=f'{user.full_name} asked to evaluate the dataset "{dataset.name}".',
            meta={"evaluation_request_id": request.id, "dataset_id": dataset.id},
        ))
    await db.commit()
    await db.refresh(request)
    await record_audit_log(db, user.id, "evaluation_requested", resource_type="evaluation_request", resource_id=request.id, details={"dataset_id": dataset_id, "top_n": request.top_n})
    return {"id": request.id, "dataset_id": dataset_id, "status": request.status, "top_n": request.top_n, "created_at": request.created_at}


@router.get("/requests")
async def list_evaluation_requests(limit: int = Query(default=50, ge=1, le=100), admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(EvaluationRequest, EvaluationDataset, User)
        .join(EvaluationDataset, EvaluationDataset.id == EvaluationRequest.dataset_id)
        .join(User, User.id == EvaluationRequest.requested_by_user_id)
        .order_by(case((EvaluationRequest.status == "pending", 0), (EvaluationRequest.status == "running", 1), else_=2), EvaluationRequest.created_at.desc())
        .limit(limit)
    )).all()
    return [{
        "id": request.id,
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "requested_by_name": requester.full_name,
        "requested_by_email": requester.email,
        "status": request.status,
        "top_n": request.top_n,
        "created_at": request.created_at,
        "completed_at": request.completed_at,
        "evaluation_result_id": request.evaluation_result_id,
    } for request, dataset, requester in rows]


@router.post("/requests/{request_id}/run")
async def run_requested_evaluation(request_id: str, payload: EvaluationSubmissionRunRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    request = (await db.execute(
        select(EvaluationRequest).where(EvaluationRequest.id == request_id).with_for_update()
    )).scalar_one_or_none()
    if not request:
        raise NotFoundError("Evaluation request not found.")
    if request.status != "pending":
        raise ConflictError(f"This evaluation request is already {request.status}.")

    request.status = "running"
    await db.commit()
    try:
        result = await run_evaluation(db, request.dataset_id, payload.top_n or request.top_n, admin.id)
    except Exception:
        await db.rollback()
        request = await db.get(EvaluationRequest, request_id)
        request.status = "failed"
        request.completed_by_user_id = admin.id
        request.completed_at = datetime.utcnow()
        requester_notice = Notification(
            user_id=request.requested_by_user_id,
            notification_type="evaluation_request",
            title="Evaluation run failed",
            message="An administrator could not complete the requested evaluation. You can resubmit it after checking the dataset labels.",
            meta={"evaluation_request_id": request.id, "dataset_id": request.dataset_id},
        )
        db.add(requester_notice)
        await db.commit()
        await record_audit_log(db, admin.id, "evaluation_run_failed", resource_type="evaluation_request", resource_id=request_id, details={"dataset_id": request.dataset_id})
        raise

    request.status = "completed"
    request.completed_by_user_id = admin.id
    request.evaluation_result_id = result.id
    request.completed_at = datetime.utcnow()
    db.add(Notification(
        user_id=request.requested_by_user_id,
        notification_type="evaluation_request",
        title="Evaluation run completed",
        message="An administrator completed your evaluation run. Refresh the dataset page to view the metrics.",
        meta={"evaluation_request_id": request.id, "dataset_id": request.dataset_id, "evaluation_result_id": result.id},
    ))
    await db.commit()
    await record_audit_log(db, admin.id, "evaluation_run_completed", resource_type="evaluation_request", resource_id=request.id, details={"dataset_id": request.dataset_id, "result_id": result.id})
    return {
        "request_id": request.id,
        "status": request.status,
        "dataset_id": request.dataset_id,
        "result": EvaluationMetricsSummaryResponse.model_validate(result).model_dump(mode="json"),
    }


@router.post("/run", response_model=EvaluationMetricsSummaryResponse)
async def run_evaluation_route(payload: EvaluationRunRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await run_evaluation(db, payload.dataset_id, payload.top_n, admin.id)
    await record_audit_log(db, admin.id, "evaluation_run_completed", resource_type="evaluation_dataset", resource_id=payload.dataset_id, details={"top_n": payload.top_n, "result_id": result.id})
    return result
