"""Planning & recommendation ORM models. Source of truth: docs/DATABASE_DESIGN.md §13–14."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.geo import City, Place  # noqa: F401
    from app.models.user import User  # noqa: F401


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id"), nullable=False
    )
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    party_size: Mapped[int] = mapped_column(nullable=False, server_default="1")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PLANNING", server_default="PLANNING"
    )
    preferences_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("ends_on >= starts_on", name="ck_trips_date_order"),
        CheckConstraint(
            "status IN ('PLANNING','BOOKED','CONFIRMED','COMPLETED','CANCELLED')",
            name="ck_trips_status",
        ),
        CheckConstraint("party_size BETWEEN 1 AND 50", name="ck_trips_party_size"),
        Index("ix_trips_user_created", "user_id", "created_at"),
    )

    city: Mapped["City"] = relationship("City")
    itinerary: Mapped["Itinerary | None"] = relationship(
        "Itinerary", back_populates="trip", uselist=False
    )


class Itinerary(Base):
    __tablename__ = "itineraries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (CheckConstraint("status IN ('ACTIVE','SUPERSEDED')", name="ck_itineraries_status"),)

    trip: Mapped["Trip"] = relationship("Trip", back_populates="itinerary")
    days: Mapped[list["ItineraryDay"]] = relationship(
        "ItineraryDay", back_populates="itinerary", cascade="all, delete-orphan",
        order_by="ItineraryDay.day_number",
    )


class ItineraryDay(Base):
    __tablename__ = "itinerary_days"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    itinerary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("itineraries.id", ondelete="CASCADE"), nullable=False
    )
    day_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("itinerary_id", "day_number", name="uq_itinerary_days_day_number"),
        CheckConstraint("day_number >= 1", name="ck_itinerary_days_day_number"),
    )

    itinerary: Mapped["Itinerary"] = relationship("Itinerary", back_populates="days")
    items: Mapped[list["ItineraryItem"]] = relationship(
        "ItineraryItem", back_populates="day", cascade="all, delete-orphan",
        order_by="ItineraryItem.position",
    )


class ItineraryItem(Base):
    __tablename__ = "itinerary_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    itinerary_day_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("itinerary_days.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    place_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("places.id"))
    custom_title: Mapped[str | None] = mapped_column(Text)
    recommendation_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendation_items.id")
    )
    start_time: Mapped[str | None] = mapped_column(Time)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("itinerary_day_id", "position", name="uq_itinerary_items_position"),
        CheckConstraint("position >= 0", name="ck_itinerary_items_position"),
        CheckConstraint(
            "place_id IS NOT NULL OR custom_title IS NOT NULL",
            name="ck_itinerary_items_reference",
        ),
        CheckConstraint("duration_minutes > 0", name="ck_itinerary_items_duration"),
    )

    day: Mapped["ItineraryDay"] = relationship("ItineraryDay", back_populates="items")
    place: Mapped["Place | None"] = relationship("Place")


class TripCompanion(Base):
    """Travelling-together sharing (Phase 8 addendum).

    The trip head (trips.user_id) invites other accounts to follow the trip.
    Companions get read-only itinerary access; bookings/payments stay
    OWNER_ONLY (§24). status lifecycle: INVITED → ACTIVE | DECLINED; the head
    can remove at any time (REMOVED) and re-invite later (new row allowed by
    reactivating this one instead).
    """

    __tablename__ = "trip_companions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    companion_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="MEMBER")
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="INVITED")
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("role IN ('HEAD','MEMBER')", name="ck_trip_companions_role"),
        CheckConstraint(
            "status IN ('INVITED','ACTIVE','DECLINED','REMOVED')",
            name="ck_trip_companions_status",
        ),
        UniqueConstraint("trip_id", "companion_user_id", name="uq_trip_companions_trip_user"),
        Index("ix_trip_companions_companion", "companion_user_id", "status"),
        Index("ix_trip_companions_trip", "trip_id"),
    )

    trip: Mapped["Trip"] = relationship("Trip")
    companion: Mapped["User"] = relationship("User", foreign_keys=[companion_user_id])


class CompanionLocationShare(Base):
    """Opt-in live location heartbeat for one traveller on one trip.

    Phase 8b addendum. A row EXISTS only while the traveller is actively
    sharing on that trip; deleting it stops sharing instantly (there is no
    paused state persisted — pausing = delete). purge_date (trip end + 1 day)
    bounds retention: GPS points are ephemeral, never historical data.
    Readable only by the trip head + ACTIVE companions of the same trip.
    """

    __tablename__ = "companion_location_shares"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    accuracy_m: Mapped[int | None] = mapped_column()
    purge_date: Mapped[date] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_location_share_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_location_share_lng"),
        UniqueConstraint("trip_id", "user_id", name="uq_location_share_trip_user"),
        Index("ix_location_shares_trip", "trip_id"),
        Index("ix_location_shares_purge", "purge_date"),
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])


class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trips.id"))
    engine_name: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="RuleBasedRecommendationEngine"
    )
    engine_version: Mapped[str] = mapped_column(Text, nullable=False)
    preference_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_recommendation_runs_user_created", "user_id", "created_at"),
        Index("ix_recommendation_runs_trip", "trip_id"),
    )

    items: Mapped[list["RecommendationItem"]] = relationship(
        "RecommendationItem", back_populates="run", cascade="all, delete-orphan",
        order_by="RecommendationItem.rank",
    )


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False
    )
    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_recommendation_items_run_rank", "run_id", "rank"),
        CheckConstraint("rank >= 1", name="ck_recommendation_items_rank"),
        CheckConstraint(
            "classification IN ('POPULAR','LESSER_KNOWN')",
            name="ck_recommendation_items_classification",
        ),
    )

    run: Mapped["RecommendationRun"] = relationship("RecommendationRun", back_populates="items")
    place: Mapped["Place"] = relationship("Place")
