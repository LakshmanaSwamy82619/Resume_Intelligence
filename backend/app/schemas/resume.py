from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ResumeUploadResponse(BaseModel):
    resume_id: str
    candidate_id: str
    processing_status: str
    is_duplicate: bool = False
    message: str


class BulkUploadResponse(BaseModel):
    processing_job_id: str
    total_files: int
    message: str


class ProcessingJobStatusResponse(BaseModel):
    id: str
    job_type: str
    status: str
    total_items: int
    processed_items: int
    failed_items: int
    duplicate_items: int
    error_summary: list
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceItem(BaseModel):
    field_type: str
    field_value: str
    evidence_text: str
    page_number: Optional[int] = None
    source_file: Optional[str] = None


class ResumeSourceItem(BaseModel):
    resume_id: str
    source_filename: str
    category: Optional[str] = None
    processing_status: str
    resume_download_url: str


class CandidateDetailResponse(BaseModel):
    candidate_id: str
    full_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    location: Optional[str]
    summary: Optional[str]
    technical_skills: list[str]
    soft_skills: list[str]
    job_titles: list[str]
    years_of_experience: Optional[float]
    profile_completeness: dict
    experience: list[dict]
    projects: list[dict]
    education: list[dict]
    certifications: list[dict]
    source_filename: Optional[str] = None
    category: Optional[str] = None
    processing_status: Optional[str] = None
    resumes: list[ResumeSourceItem] = Field(default_factory=list)
    resume_download_url: Optional[str] = None
