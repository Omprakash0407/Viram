"""Schemas for community suggestions (§14) and the admin audit log (§32)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SuggestionCreate(BaseModel):
    submitter_name: str = Field(min_length=2, max_length=120)
    contact: str | None = Field(default=None, max_length=160)
    kind: str
    title: str = Field(min_length=5, max_length=200)
    body: str = Field(min_length=20, max_length=6000)
    city_id: uuid.UUID | None = None
    place_id: uuid.UUID | None = None


class SuggestionOut(BaseModel):
    id: uuid.UUID
    submitter_name: str
    kind: str
    title: str
    body: str
    status: str
    admin_note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SuggestionList(BaseModel):
    items: list[SuggestionOut]


class SuggestionReview(BaseModel):
    decision: str  # APPROVED | REJECTED
    admin_note: str | None = Field(default=None, max_length=2000)
