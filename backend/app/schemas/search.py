from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class JobDescriptionCreateRequest(BaseModel):
    raw_text: str = Field(min_length=10)
    title: Optional[str] = None
    input_mode: Literal["uploaded", "pasted", "natural_language", "structured"] = "pasted"


class JobDescriptionResponse(BaseModel):
    id: str
    title: Optional[str]
    raw_text: str
    input_mode: str
    source_filename: Optional[str] = None
    mandatory_requirements: list[dict]
    preferred_requirements: list[dict]
    min_experience_years: Optional[float]
    preferred_experience_years: Optional[float]
    llm_enrichment_used: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateFilters(BaseModel):
    min_experience_years: Optional[float] = Field(default=None, ge=0)
    max_experience_years: Optional[float] = Field(default=None, ge=0)
    skills: list[str] = Field(default_factory=list, max_length=20)
    education: list[str] = Field(default_factory=list, max_length=20)
    certifications: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_experience_range(self):
        if self.min_experience_years is not None and self.max_experience_years is not None and self.max_experience_years < self.min_experience_years:
            raise ValueError("Maximum experience must be greater than or equal to minimum experience.")
        return self


class SearchRequest(BaseModel):
    job_description_id: Optional[str] = None
    query_text: Optional[str] = Field(default=None, description="Optional additional hiring requirements to combine with a saved job brief.")
    top_n: Literal[3, 5] = 5
    candidate_filters: CandidateFilters = Field(default_factory=CandidateFilters)

    def resolve_query(self) -> str:
        return self.query_text or ""


class RequirementFindingResponse(BaseModel):
    requirement: str
    requirement_type: str
    priority: str
    status: str
    evidence_text: Optional[str] = None
    page_number: Optional[int] = None
    source_file: Optional[str] = None
    note: Optional[str] = None


class CandidateSearchResult(BaseModel):
    rank: int
    candidate_id: str
    candidate_name: Optional[str]
    resume_id: Optional[str]
    resume_download_url: Optional[str]
    final_score: float
    score_breakdown: dict
    matched_requirements: list[RequirementFindingResponse]
    partial_requirements: list[RequirementFindingResponse]
    missing_requirements: list[RequirementFindingResponse]
    years_of_experience: Optional[float]
    relevant_projects: list[dict]
    relevant_experience: list[dict]
    why_selected_summary: str
    why_selected_points: list[str]
    evidence: list[dict]
    validation_status: str
    validation_notes: list[dict]


class SearchResponse(BaseModel):
    search_id: str
    top_n_requested: int
    resumes_considered: int
    candidate_pool_size: int
    retrieval_method: str
    processing_time_ms: Optional[float]
    ai_provider: Optional[str]
    fallback_used: bool
    fallback_reason: Optional[str]
    processing_mode: Optional[str]
    provider_status: dict
    applied_filters: dict = Field(default_factory=dict)
    processing_pipeline: dict = Field(default_factory=dict)
    results: list[CandidateSearchResult]


class SearchHistoryItem(BaseModel):
    id: str
    query_text: str
    top_n_requested: int
    resumes_considered: int
    candidate_pool_size: int
    fallback_used: bool
    processing_time_ms: Optional[float]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompareCandidatesRequest(BaseModel):
    search_id: str
    candidate_ids: list[str] = Field(min_length=2, max_length=5)


class JobRequirementUpdate(BaseModel):
    requirement_type: Literal["skill", "technology", "domain", "responsibility", "education", "certification"] = "skill"
    value: str = Field(min_length=1, max_length=500)
    priority: Literal["mandatory", "preferred"] = "mandatory"


class JobRequirementsUpdateRequest(BaseModel):
    requirements: list[JobRequirementUpdate] = Field(max_length=100)


class ShortlistExportRequest(BaseModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=5)
    format: Literal["csv", "pdf"]
