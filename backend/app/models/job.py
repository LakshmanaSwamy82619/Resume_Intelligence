from __future__ import annotations

from typing import Optional

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RequirementPriority
from app.models.mixins import IdMixin, TimestampMixin


class JobDescription(Base, IdMixin, TimestampMixin):
    __tablename__ = "job_descriptions"

    created_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    input_mode: Mapped[str] = mapped_column(String(30), default="pasted")  # uploaded/pasted/natural_language/structured
    source_filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    llm_enrichment_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    extracted_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extracted_education: Mapped[list] = mapped_column(JSON, default=list)
    extracted_certifications: Mapped[list] = mapped_column(JSON, default=list)
    extracted_responsibilities: Mapped[list] = mapped_column(JSON, default=list)
    min_experience_years: Mapped[Optional[float]] = mapped_column(nullable=True)
    preferred_experience_years: Mapped[Optional[float]] = mapped_column(nullable=True)

    requirements: Mapped[list["JobRequirement"]] = relationship(back_populates="job_description", cascade="all, delete-orphan")


class JobRequirement(Base, IdMixin, TimestampMixin):
    __tablename__ = "job_requirements"

    job_description_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(50), nullable=False)  # skill/technology/domain/responsibility
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default=RequirementPriority.PREFERRED.value)

    job_description: Mapped[JobDescription] = relationship(back_populates="requirements")
