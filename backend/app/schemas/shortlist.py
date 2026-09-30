from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ShortlistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    search_id: Optional[str] = None
    candidate_ids: list[str] = Field(default_factory=list, max_length=100)


class ShortlistCandidateAddRequest(BaseModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=100)
    search_id: Optional[str] = None


class ShortlistUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class ShortlistCandidateUpdateRequest(BaseModel):
    stage: Optional[Literal["saved", "screening", "interview", "accepted", "offer", "hired", "rejected"]] = None
    notes: Optional[str] = Field(default=None, max_length=4000)
