"""Schemas for provider profiles and identity verification.

Visibility rules baked into the shapes (§24):
- review_note / reviewed_by / reviewed_at NEVER appear on public or owner
  shapes — ADMIN_ONLY data stays admin-only.
- Owner shapes expose status so providers can see where they stand.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

CATEGORIES = [
    "CAFE", "RESTAURANT", "ARTISAN", "HANDICRAFT",
    "HOMESTAY", "FOOD", "TOUR", "EXPERIENCE", "OTHER",
]


# ---------- Guide profile (§3) ----------

class GuideProfileUpsert(BaseModel):
    public_name: str = Field(min_length=2, max_length=200)
    bio: str | None = Field(default=None, max_length=4000)
    languages: list[str] = Field(default_factory=list, max_length=20)
    expertise: list[str] = Field(default_factory=list, max_length=20)
    areas_served: list[str] = Field(default_factory=list, max_length=20)
    city_id: uuid.UUID | None = None
    day_rate_paise: int | None = Field(default=None, gt=0)


class GuideProfileOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    public_name: str
    bio: str | None
    languages: list[str]
    expertise: list[str]
    areas_served: list[str]
    city_id: uuid.UUID | None
    day_rate_paise: int | None
    currency: str
    status: str
    visibility: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Business profile (§4) ----------

class BusinessProfileCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=6000)
    category: str
    city_id: uuid.UUID
    place_id: uuid.UUID | None = None
    services: list[str] = Field(default_factory=list, max_length=30)
    public_phone: str | None = Field(default=None, max_length=40)
    public_email: str | None = Field(default=None, max_length=160)
    public_address: str | None = Field(default=None, max_length=300)


class BusinessProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=6000)
    category: str | None = None
    place_id: uuid.UUID | None = None
    services: list[str] | None = Field(default=None, max_length=30)
    public_phone: str | None = Field(default=None, max_length=40)
    public_email: str | None = Field(default=None, max_length=160)
    public_address: str | None = Field(default=None, max_length=300)


class BusinessProfileOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    category: str
    state_id: uuid.UUID
    city_id: uuid.UUID
    place_id: uuid.UUID | None
    services: list[str]
    public_phone: str | None
    public_email: str | None
    public_address: str | None
    status: str
    visibility: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BusinessPublicOut(BaseModel):
    """Public shape (§24): approved + public rows only, owner never exposed."""

    id: uuid.UUID
    name: str
    description: str | None
    category: str
    city_id: uuid.UUID
    place_id: uuid.UUID | None
    services: list[str]
    public_phone: str | None
    public_email: str | None
    public_address: str | None

    model_config = {"from_attributes": True}


class BusinessList(BaseModel):
    items: list[BusinessPublicOut]
    total: int


# ---------- Identity verification (Phase 7 addendum) ----------

class IdentityVerificationOut(BaseModel):
    id: uuid.UUID
    provider: str
    id_proof_type: str
    status: str
    requested_at: datetime
    verified_at: datetime | None
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class IdentityStatus(BaseModel):
    identity_verified: bool
    latest: IdentityVerificationOut | None
    demo_note: str


class IdentityInitOut(BaseModel):
    verification: IdentityVerificationOut
    consent_url: str
    demo_note: str


# ---------- Admin review ----------

class ProviderReview(BaseModel):
    decision: str  # APPROVED | REJECTED | SUSPENDED | REINSTATE
    admin_note: str | None = Field(default=None, max_length=2000)


class AdminProviderOut(BaseModel):
    """Admin queue shape — includes reviewer data (ADMIN_ONLY fields allowed)."""

    kind: str  # GUIDE | BUSINESS
    id: uuid.UUID
    user_id: uuid.UUID
    owner_email: str | None
    owner_identity_verified: bool
    name: str
    category: str | None
    city_id: uuid.UUID | None
    status: str
    visibility: str
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
