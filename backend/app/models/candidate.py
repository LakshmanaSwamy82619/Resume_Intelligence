from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base, PortableVector
from app.models.enums import ProcessingStatus
from app.models.mixins import IdMixin, TimestampMixin

settings = get_settings()


class Candidate(Base, IdMixin, TimestampMixin):
    """The structured, de-duplicated candidate entity. One candidate can
    (rarely) have more than one Resume on file (re-uploads); the latest
    successfully processed resume drives the structured fields below.
    """

    __tablename__ = "candidates"

    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Structured, evidence-backed extraction (each item below is a dict
    # containing at least {"value": ..., "evidence_ids": [...]})
    skills: Mapped[list] = mapped_column(JSON, default=list)
    technical_skills: Mapped[list] = mapped_column(JSON, default=list)
    soft_skills: Mapped[list] = mapped_column(JSON, default=list)
    job_titles: Mapped[list] = mapped_column(JSON, default=list)
    responsibilities: Mapped[list] = mapped_column(JSON, default=list)
    project_technologies: Mapped[list] = mapped_column(JSON, default=list)
    achievements: Mapped[list] = mapped_column(JSON, default=list)
    languages: Mapped[list] = mapped_column(JSON, default=list)

    years_of_experience: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Fingerprint used for duplicate detection (Section 27)
    fingerprint: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)

    resumes: Mapped[list["Resume"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    experience: Mapped[list["CandidateExperience"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    projects: Mapped[list["CandidateProject"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    education: Mapped[list["CandidateEducation"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    certifications: Mapped[list["CandidateCertification"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")


class Resume(Base, IdMixin, TimestampMixin):
    __tablename__ = "resumes"

    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    uploaded_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source_relative_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    file_hash: Mapped[str] = mapped_column(String(128), index=True, nullable=False)

    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extraction_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # pdf_text/pdf_ocr/docx/txt
    used_ocr: Mapped[bool] = mapped_column(default=False)

    processing_status: Mapped[str] = mapped_column(String(20), default=ProcessingStatus.PENDING.value)
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_duplicate_of_resume_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="resumes")
    chunks: Mapped[list["ResumeChunk"]] = relationship(back_populates="resume", cascade="all, delete-orphan")
    evidence: Mapped[list["ResumeEvidence"]] = relationship(back_populates="resume", cascade="all, delete-orphan")


class ResumeChunk(Base, IdMixin, TimestampMixin):
    """A retrieval-unit chunk of a resume (section- or paragraph-scoped),
    embedded independently so retrieval can match on the specific part of
    the resume that is relevant, not just a single whole-document vector.
    """

    __tablename__ = "resume_chunks"

    resume_id: Mapped[str] = mapped_column(String(36), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # skills/experience/projects/education/...
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    embedding: Mapped[Optional[list]] = mapped_column(PortableVector(settings.VECTOR_DIMENSION), nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    resume: Mapped[Resume] = relationship(back_populates="chunks")


class ResumeEvidence(Base, IdMixin, TimestampMixin):
    """One traceable fact: an extracted field value plus the exact source
    text/location it was derived from (Section 7 - mandatory).
    """

    __tablename__ = "resume_evidence"

    resume_id: Mapped[str] = mapped_column(String(36), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)

    field_type: Mapped[str] = mapped_column(String(50), nullable=False)  # skill/experience/project/education/certification
    field_value: Mapped[str] = mapped_column(String(500), nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("resume_chunks.id"), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    resume: Mapped[Resume] = relationship(back_populates="evidence")


class CandidateExperience(Base, IdMixin, TimestampMixin):
    __tablename__ = "candidate_experience"

    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    end_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    duration_years: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    responsibilities_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("resume_evidence.id"), nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="experience")


class CandidateProject(Base, IdMixin, TimestampMixin):
    __tablename__ = "candidate_projects"

    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    technologies: Mapped[list] = mapped_column(JSON, default=list)
    evidence_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("resume_evidence.id"), nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="projects")


class CandidateEducation(Base, IdMixin, TimestampMixin):
    __tablename__ = "candidate_education"

    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    degree: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    institution: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    field_of_study: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    end_year: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    evidence_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("resume_evidence.id"), nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="education")


class CandidateCertification(Base, IdMixin, TimestampMixin):
    __tablename__ = "candidate_certifications"

    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    issuer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    year: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    evidence_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("resume_evidence.id"), nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="certifications")
