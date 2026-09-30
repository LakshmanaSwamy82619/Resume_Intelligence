from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EvaluationDatasetCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class EvaluationQueryCreateRequest(BaseModel):
    query_text: str


class EvaluationLabelCreateRequest(BaseModel):
    candidate_id: str
    relevance: int = Field(ge=0, le=2, description="0=not relevant, 1=relevant, 2=highly relevant")
    skill_statuses: dict[str, Literal["matched", "partial", "missing"]] = Field(default_factory=dict)


class EvaluationRunRequest(BaseModel):
    dataset_id: str
    top_n: int = 5


class EvaluationSubmissionRunRequest(BaseModel):
    top_n: Optional[Literal[3, 5, 10]] = None


class EvaluationRequestCreateRequest(BaseModel):
    top_n: Literal[3, 5, 10] = 5


class EvaluationMetricsSummaryResponse(BaseModel):
    id: str
    dataset_id: str
    top_n: int
    metrics: dict
    notes: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationResultResponse(BaseModel):
    id: str
    dataset_id: str
    top_n: int
    metrics: dict
    per_query_results: list
    notes: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SystemHealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    celery: str
    llm_provider: str
    embedding_provider: str
    reranker_provider: str


class AdminAnalyticsResponse(BaseModel):
    total_resumes: int
    processed_resumes: int
    partial_resumes: int
    failed_resumes: int
    pending_resumes: int
    total_candidates: int
    total_searches: int
    top3_searches: int
    top5_searches: int
    total_hr_users: int
    active_hr_users: int
    fallback_usage_rate: float
    avg_search_latency_ms: Optional[float]
