"""Geography ORM models. Source of truth: docs/DATABASE_DESIGN.md §7."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def slugify(value: str) -> str:
    """URL-safe slug: lowercase, alphanumerics and hyphens only."""
    import re

    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


class State(Base):
    __tablename__ = "states"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(140), nullable=False, unique=True)


class City(Base):
    __tablename__ = "cities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("states.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)

    __table_args__ = (
        UniqueConstraint("state_id", "name", name="uq_cities_state_name"),
        UniqueConstraint("state_id", "slug", name="uq_cities_state_slug"),
    )

    state: Mapped["State"] = relationship("State")


class PlaceCategory(Base):
    __tablename__ = "place_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)


class Place(Base):
    __tablename__ = "places"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("place_categories.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    classification: Mapped[str] = mapped_column(
        String(20), nullable=False, default="POPULAR", server_default="POPULAR"
    )
    lesser_known_note: Mapped[str | None] = mapped_column(Text)
    popularity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    rating_avg: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    review_count: Mapped[int] = mapped_column(nullable=False, server_default="0")
    typical_visit_minutes: Mapped[int | None] = mapped_column(Integer)
    opening_hours: Mapped[str | None] = mapped_column(String(200))
    # Editorial detail payload (tagline, experiences, travel tips, gallery
    # URLs, nearby links). Nullable: places without curated details render
    # from base fields only. Admin-managed, never user-generated.
    details: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("city_id", "slug", name="uq_places_city_slug"),
        CheckConstraint(
            "classification IN ('POPULAR','LESSER_KNOWN')", name="ck_places_classification"
        ),
        CheckConstraint(
            "classification <> 'LESSER_KNOWN' OR lesser_known_note IS NOT NULL",
            name="ck_places_lesser_known_note",
        ),
        CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="ck_places_status"),
        CheckConstraint("review_count >= 0", name="ck_places_review_count"),
    )

    city: Mapped["City"] = relationship("City")
    category: Mapped["PlaceCategory"] = relationship("PlaceCategory")
