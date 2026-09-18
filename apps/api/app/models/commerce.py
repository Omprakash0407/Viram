"""Commerce ORM models. Source of truth: docs/DATABASE_DESIGN.md §15, §16, §18, §23.

- Money is integer paise (never floats) with currency CHAR(3) (§0, D15).
- Bookings are separate typed tables with a shared status vocabulary (D4).
- Payments link to bookings via two typed nullable FKs, at least one set (D5).
- No per-night hotel inventory exists; `declared_units` is informational (D6).
- Hotels are admin-managed in the MVP: no user owner (D7).
- `admin_audit_log` is append-only — no updates, no deletes (§23).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.geo import City  # noqa: F401
    from app.models.planning import Trip  # noqa: F401
    from app.models.user import User  # noqa: F401

BOOKING_STATUSES = "('PENDING_PAYMENT','CONFIRMED','CANCELLED','COMPLETED','REFUNDED')"


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    amenities: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    public_phone: Mapped[str | None] = mapped_column(Text)
    public_email: Mapped[str | None] = mapped_column(Text)
    public_address: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("city_id", "slug", name="uq_hotels_city_slug"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_hotels_status"),
    )

    city: Mapped["City"] = relationship("City")
    room_types: Mapped[list["RoomType"]] = relationship(
        "RoomType", back_populates="hotel", cascade="all, delete-orphan"
    )


class RoomType(Base):
    __tablename__ = "room_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    nightly_rate_paise: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="INR")
    declared_units: Mapped[int | None] = mapped_column(Integer)  # informational only (D6)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "name", name="uq_room_types_hotel_name"),
        CheckConstraint("capacity BETWEEN 1 AND 10", name="ck_room_types_capacity"),
        CheckConstraint("nightly_rate_paise > 0", name="ck_room_types_rate"),
    )

    hotel: Mapped["Hotel"] = relationship("Hotel", back_populates="room_types")


class HotelBooking(Base):
    __tablename__ = "hotel_bookings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    reference_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trips.id"))
    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    room_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("room_types.id"), nullable=False
    )
    check_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    check_out_date: Mapped[date] = mapped_column(Date, nullable=False)
    rooms_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    price_snapshot_paise: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="INR")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING_PAYMENT", server_default="PENDING_PAYMENT"
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    external_reference: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("check_out_date > check_in_date", name="ck_hotel_bookings_dates"),
        CheckConstraint(f"status IN {BOOKING_STATUSES}", name="ck_hotel_bookings_status"),
        CheckConstraint("rooms_count >= 1", name="ck_hotel_bookings_rooms"),
        CheckConstraint("price_snapshot_paise > 0", name="ck_hotel_bookings_price"),
        Index("ix_hotel_bookings_user_created", "user_id", "created_at"),
        Index("ix_hotel_bookings_status_checkin", "status", "check_in_date"),
    )

    user: Mapped["User"] = relationship("User")
    trip: Mapped["Trip | None"] = relationship("Trip")
    hotel: Mapped["Hotel"] = relationship("Hotel")
    room_type: Mapped["RoomType"] = relationship("RoomType")


class GuideProfile(Base):
    __tablename__ = "guide_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    public_name: Mapped[str] = mapped_column(String(200), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text)
    languages: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    expertise: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    areas_served: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    city_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cities.id"))
    day_rate_paise: Mapped[int | None] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="INR")
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
            name="ck_guide_profiles_status",
        ),
        CheckConstraint("visibility IN ('PUBLIC','PRIVATE')", name="ck_guide_profiles_visibility"),
        CheckConstraint("day_rate_paise IS NULL OR day_rate_paise > 0", name="ck_guide_profiles_rate"),
        Index(
            "ix_guide_profiles_city_public",
            "city_id",
            postgresql_where=sa.text("status = 'APPROVED' AND visibility = 'PUBLIC'"),
        ),
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    city: Mapped["City | None"] = relationship("City")


class GuideAvailability(Base):
    __tablename__ = "guide_availability"

    guide_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guide_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    service_date: Mapped[date] = mapped_column(Date, primary_key=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="AVAILABLE")
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status IN ('AVAILABLE','UNAVAILABLE','BUSY')",
            name="ck_guide_availability_status",
        ),
        Index("ix_guide_availability_service_date", "service_date"),
    )

    guide: Mapped["GuideProfile"] = relationship("GuideProfile")


class GuideBooking(Base):
    __tablename__ = "guide_bookings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    reference_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trips.id"))
    guide_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guide_profiles.id"), nullable=False
    )
    service_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    service_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    price_snapshot_paise: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="INR")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING_PAYMENT", server_default="PENDING_PAYMENT"
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "service_end_date >= service_start_date", name="ck_guide_bookings_dates"
        ),
        CheckConstraint(f"status IN {BOOKING_STATUSES}", name="ck_guide_bookings_status"),
        CheckConstraint("price_snapshot_paise > 0", name="ck_guide_bookings_price"),
        Index("ix_guide_bookings_user_created", "user_id", "created_at"),
        Index(
            "ix_guide_bookings_guide_status_start",
            "guide_profile_id",
            "status",
            "service_start_date",
        ),
        Index("ix_guide_bookings_status_start", "status", "service_start_date"),
    )

    user: Mapped["User"] = relationship("User")
    trip: Mapped["Trip | None"] = relationship("Trip")
    guide: Mapped["GuideProfile"] = relationship("GuideProfile")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    hotel_booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotel_bookings.id")
    )
    guide_booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guide_bookings.id")
    )
    gateway: Mapped[str] = mapped_column(String(40), nullable=False)
    gateway_order_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    gateway_payment_id: Mapped[str | None] = mapped_column(Text, unique=True)
    amount_paise: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="INR")
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="CREATED")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "hotel_booking_id IS NOT NULL OR guide_booking_id IS NOT NULL",
            name="ck_payments_booking_link",
        ),
        CheckConstraint("amount_paise > 0", name="ck_payments_amount"),
        CheckConstraint(
            "status IN ('CREATED','PENDING','SUCCEEDED','FAILED','REFUNDED')",
            name="ck_payments_status",
        ),
        Index("ix_payments_user_created", "user_id", "created_at"),
    )

    user: Mapped["User"] = relationship("User")
    hotel_booking: Mapped["HotelBooking | None"] = relationship("HotelBooking")
    guide_booking: Mapped["GuideBooking | None"] = relationship("GuideBooking")


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False
    )
    amount_paise: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="INR")
    gateway_refund_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="REQUESTED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="ck_refunds_amount"),
        CheckConstraint(
            "status IN ('REQUESTED','PROCESSING','PROCESSED','FAILED')",
            name="ck_refunds_status",
        ),
    )

    payment: Mapped["Payment"] = relationship("Payment")


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhook_events"

    provider: Mapped[str] = mapped_column(String(40), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(60), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_admin_audit_log_target", "target_type", "target_id"),
        Index("ix_admin_audit_log_created", "created_at"),
    )

    admin: Mapped["User"] = relationship("User")
