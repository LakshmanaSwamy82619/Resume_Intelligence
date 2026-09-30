from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import IdMixin, TimestampMixin


class Search(Base, IdMixin, TimestampMixin):
    __tablename__ = "searches"

    hr_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    job_description_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("job_descriptions.id"), nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_requirements: Mapped[dict] = mapped_column(JSON, default=dict)

    top_n_requested: Mapped[int] = mapped_column(Integer, default=5)
    retrieval_method: Mapped[str] = mapped_column(String(30), default="hybrid")
    resumes_considered: Mapped[int] = mapped_column(Integer, default=0)
    candidate_pool_size: Mapped[int] = mapped_column(Integer, default=0)

    processing_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ai_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    processing_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # full_ai / partial_fallback / deterministic

    evaluation: Mapped[dict] = mapped_column(JSON, default=dict)

    candidates: Mapped[list["SearchCandidate"]] = relationship(back_populates="search", cascade="all, delete-orphan")


class SearchCandidate(Base, IdMixin, TimestampMixin):
    """One ranked candidate result within a Search, with everything needed
    for the 'Why this candidate?' explanation (Section 19/20).
    """

    __tablename__ = "search_candidates"

    search_id: Mapped[str] = mapped_column(String(36), ForeignKey("searches.id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"), nullable=False)
    resume_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("resumes.id"), nullable=True)

    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    lexical_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    semantic_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hybrid_retrieval_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reranker_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)

    matched_requirements: Mapped[list] = mapped_column(JSON, default=list)
    partial_requirements: Mapped[list] = mapped_column(JSON, default=list)
    missing_requirements: Mapped[list] = mapped_column(JSON, default=list)

    explanation_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explanation_points: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    validation_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # validated/flagged
    validation_notes: Mapped[list] = mapped_column(JSON, default=list)

    search: Mapped[Search] = relationship(back_populates="candidates")


class EvaluationDataset(Base, IdMixin, TimestampMixin):
    __tablename__ = "evaluation_datasets"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    queries: Mapped[list["EvaluationQuery"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class EvaluationQuery(Base, IdMixin, TimestampMixin):
    __tablename__ = "evaluation_queries"

    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)

    dataset: Mapped[EvaluationDataset] = relationship(back_populates="queries")
    labels: Mapped[list["EvaluationLabel"]] = relationship(back_populates="query", cascade="all, delete-orphan")


class EvaluationLabel(Base, IdMixin, TimestampMixin):
    """Human-provided relevance label for (query, candidate) — ground truth,
    never invented by the system (Section 23).
    """

    __tablename__ = "evaluation_labels"

    query_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_queries.id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"), nullable=False)
    relevance: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=not relevant, 1=relevant, 2=highly relevant
    skill_statuses: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    labeled_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    query: Mapped[EvaluationQuery] = relationship(back_populates="labels")


class EvaluationResult(Base, IdMixin, TimestampMixin):
    """A single evaluation run's computed metrics against a dataset."""

    __tablename__ = "evaluation_results"

    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_datasets.id"), nullable=False)
    triggered_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    top_n: Mapped[int] = mapped_column(Integer, default=5)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)  # precision@k, recall@k, mrr, ndcg, etc.
    per_query_results: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class EvaluationRequest(Base, IdMixin, TimestampMixin):
    """HR request for an administrator to run metrics on a labeled dataset."""

    __tablename__ = "evaluation_requests"

    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    top_n: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    completed_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    evaluation_result_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("evaluation_results.id"), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ProcessingJob(Base, IdMixin, TimestampMixin):
    __tablename__ = "processing_jobs"

    job_type: Mapped[str] = mapped_column(String(30), nullable=False)  # single_resume/bulk_resume/reindex
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    processed_items: Mapped[int] = mapped_column(Integer, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_items: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[list] = mapped_column(JSON, default=list)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(155), nullable=True)
