"""Provider & identity models (design doc §4 BusinessProfile; Phase 7 addendum
for DigiLocker-style identity verification).

- BusinessProfile: 0..N per user (a business owner may own several), powers the
  Local Partners wall (§17) and business discovery. Entity-level verification
  status exactly like GuideProfile (§5).
- IdentityVerification: DigiLocker-style identity proofing. SECURITY RULE: the
  Aadhaar number (or any full document number) is NEVER stored, transmitted
  into the database, or logged — only the verification status, the issuing
  provider's own reference id, and timestamps. The schema has no column that
  could hold a document number (mirrors the payments rule of §18).
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import User

BUSINESS_CATEGORIES = (
    "CAFE",
    "RESTAURANT",
    "ARTISAN",
    "HANDICRAFT",
    "HOMESTAY",
    "FOOD",
    "TOUR",
    "EXPERIENCE",
    "OTHER",
)


class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("states.id"), nullable=False
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id"), nullable=False
    )
    place_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id")
    )
    services: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    public_phone: Mapped[str | None] = mapped_column(Text)
    public_email: Mapped[str | None] = mapped_column(Text)
    public_address: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="PENDING")
    visibility: Mapped[str] = mapped_column(String(10), nullable=False, server_default="PRIVATE")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)  # ADMIN_ONLY (§24)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','SUSPENDED')",
            name="ck_business_profiles_status",
        ),
        CheckConstraint("visibility IN ('PUBLIC','PRIVATE')", name="ck_business_profiles_visibility"),
        CheckConstraint(f"category IN {BUSINESS_CATEGORIES}", name="ck_business_profiles_category"),
        Index(
            "ix_business_profiles_city_public",
            "city_id",
            postgresql_where=sa.text("status = 'APPROVED' AND visibility = 'PUBLIC'"),
        ),
        Index("ix_business_profiles_owner", "user_id", "created_at"),
        Index("ix_business_profiles_category_public", "category",
              postgresql_where=sa.text("status = 'APPROVED' AND visibility = 'PUBLIC'")),
    )

    owner: Mapped["User"] = relationship("User", foreign_keys=[user_id])


class IdentityVerification(Base):
    __tablename__ = "identity_verifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False, server_default="DIGILOCKER_DEMO")
    id_proof_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="AADHAAR")
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="PENDING")
    provider_reference: Mapped[str | None] = mapped_column(Text)  # provider's own ref; never a document number
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "provider IN ('DIGILOCKER_DEMO','DIGILOCKER','MANUAL_ADMIN')",
            name="ck_identity_verifications_provider",
        ),
        CheckConstraint(
            "id_proof_type IN ('AADHAAR','DRIVING_LICENCE','VOTER_ID','PASSPORT')",
            name="ck_identity_verifications_proof_type",
        ),
        CheckConstraint(
            "status IN ('PENDING','APPROVED','FAILED','EXPIRED')",
            name="ck_identity_verifications_status",
        ),
        Index("ix_identity_verifications_user_status", "user_id", "status"),
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])


# UniqueConstraint import kept for symmetry with the other model modules.
_ = UniqueConstraint
