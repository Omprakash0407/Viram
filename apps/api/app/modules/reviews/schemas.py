"""Request/response schemas for place reviews (design doc §24)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=140)
    body: str = Field(min_length=10, max_length=4000)
    visited_on: str | None = Field(default=None, max_length=20)


class ReviewAuthor(BaseModel):
    display_name: str


class ReviewOut(BaseModel):
    id: uuid.UUID
    rating: int
    title: str | None
    body: str
    status: str
    visited_on: str | None
    created_at: datetime
    author: ReviewAuthor

    model_config = {"from_attributes": True}


class ReviewList(BaseModel):
    items: list[ReviewOut]
    rating_avg: float | None
    review_count: int


class ReviewCreateResponse(BaseModel):
    review: ReviewOut
    rating_avg: float | None
    review_count: int
