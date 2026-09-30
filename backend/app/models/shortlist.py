from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import IdMixin, TimestampMixin


class RecruiterShortlist(Base, IdMixin, TimestampMixin):
    __tablename__ = "recruiter_shortlists"

    owner_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    search_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("searches.id", ondelete="SET NULL"), nullable=True)

    candidates: Mapped[list["RecruiterShortlistCandidate"]] = relationship(
        back_populates="shortlist", cascade="all, delete-orphan", order_by="RecruiterShortlistCandidate.created_at"
    )


class RecruiterShortlistCandidate(Base, IdMixin, TimestampMixin):
    __tablename__ = "recruiter_shortlist_candidates"
    __table_args__ = (UniqueConstraint("shortlist_id", "candidate_id", name="uq_shortlist_candidate"),)

    shortlist_id: Mapped[str] = mapped_column(String(36), ForeignKey("recruiter_shortlists.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    source_search_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("searches.id", ondelete="SET NULL"), nullable=True)
    stage: Mapped[str] = mapped_column(String(30), default="saved", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    shortlist: Mapped[RecruiterShortlist] = relationship(back_populates="candidates")
