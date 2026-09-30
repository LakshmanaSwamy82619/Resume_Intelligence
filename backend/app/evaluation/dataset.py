from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.search import EvaluationDataset, EvaluationLabel, EvaluationQuery


async def create_dataset(db: AsyncSession, name: str, description: str | None, created_by_user_id: str) -> EvaluationDataset:
    dataset = EvaluationDataset(name=name, description=description, created_by_user_id=created_by_user_id)
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


async def add_query(db: AsyncSession, dataset_id: str, query_text: str) -> EvaluationQuery:
    query = EvaluationQuery(dataset_id=dataset_id, query_text=query_text)
    db.add(query)
    await db.commit()
    await db.refresh(query)
    return query


async def add_label(db: AsyncSession, query_id: str, candidate_id: str, relevance: int, labeled_by_user_id: str, skill_statuses: dict | None = None) -> EvaluationLabel:
    label = (await db.execute(select(EvaluationLabel).where(EvaluationLabel.query_id == query_id, EvaluationLabel.candidate_id == candidate_id))).scalar_one_or_none()
    if label is None:
        label = EvaluationLabel(query_id=query_id, candidate_id=candidate_id, relevance=relevance, labeled_by_user_id=labeled_by_user_id, skill_statuses=skill_statuses or {})
        db.add(label)
    else:
        label.relevance = relevance
        label.labeled_by_user_id = labeled_by_user_id
        label.skill_statuses = skill_statuses or {}
    await db.commit()
    await db.refresh(label)
    return label


async def get_dataset_with_queries(db: AsyncSession, dataset_id: str) -> EvaluationDataset | None:
    stmt = (
        select(EvaluationDataset)
        .where(EvaluationDataset.id == dataset_id)
        .options(selectinload(EvaluationDataset.queries).selectinload(EvaluationQuery.labels))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
