"""Intelligence + safety models (design doc §27–§29).

Snapshots are caches of external truth, never presented as live guarantees
(weather/routes carry provider + retrieval timestamps and are replaced, not
accumulated); emergency data is maintained separately from traveller-generated
content (admin/seed managed only).
"""

import uuid

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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WeatherSnapshot(Base):
    """Cached weather for a city + date (design doc §27).

    Re-reads upsert the (city, date, provider) row — a cache, not a log.
    """

    __tablename__ = "weather_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # ISO date
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    temperature_c: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    condition: Mapped[str] = mapped_column(String(60), nullable=False)
    humidity_pct: Mapped[int | None] = mapped_column(Integer)
    wind_kmph: Mapped[float | None] = mapped_column(Numeric(5, 1))
    payload: Mapped[dict | None] = mapped_column(JSONB)  # provider extras
    retrieved_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("city_id", "date", "provider", name="uq_weather_city_date_provider"),
        CheckConstraint("temperature_c >= -90 AND temperature_c <= 60", name="ck_weather_temp"),
    )


class RouteSnapshot(Base):
    """Cached route between two points (design doc §28).

    Origin/destination are freeform labels + coords (Place, Hotel, Business or
    custom location all collapse to coordinates at snapshot time).
    """

    __tablename__ = "route_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    origin_label: Mapped[str] = mapped_column(String(160), nullable=False)
    origin_lat: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    origin_lng: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    destination_label: Mapped[str] = mapped_column(String(160), nullable=False)
    destination_lat: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    destination_lng: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    distance_km: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    polyline: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    retrieved_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("distance_km >= 0", name="ck_route_distance_nonneg"),
        CheckConstraint("duration_min >= 0", name="ck_route_duration_nonneg"),
    )


class EmergencyFacility(Base):
    """Hospitals/healthcare/police etc. (design doc §29) — admin-managed."""

    __tablename__ = "emergency_facilities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # HOSPITAL | CLINIC | PHARMACY | POLICE | FIRE_STATION | TOURIST_HELP
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(30))
    is_24x7: Mapped[bool] = mapped_column(nullable=False, default=False)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)

    __table_args__ = (
        UniqueConstraint("city_id", "name", name="uq_emergency_facility_city_name"),
        CheckConstraint(
            "kind IN ('HOSPITAL','CLINIC','PHARMACY','POLICE','FIRE_STATION','TOURIST_HELP')",
            name="ck_emergency_facility_kind",
        ),
    )


class EmergencyContact(Base):
    """City/state/national emergency numbers (design doc §29) — admin-managed."""

    __tablename__ = "emergency_contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    # NATIONAL | STATE | CITY — at most one of the three scopes is set
    scope: Mapped[str] = mapped_column(String(10), nullable=False)
    state_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("states.id", ondelete="CASCADE")
    )
    city_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id", ondelete="CASCADE")
    )
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("scope IN ('NATIONAL','STATE','CITY')", name="ck_emergency_contact_scope"),
        CheckConstraint(
            "(scope = 'NATIONAL' AND state_id IS NULL AND city_id IS NULL)"
            " OR (scope = 'STATE' AND state_id IS NOT NULL AND city_id IS NULL)"
            " OR (scope = 'CITY' AND city_id IS NOT NULL AND state_id IS NULL)",
            name="ck_emergency_contact_scope_shape",
        ),
    )


class CommunitySuggestion(Base):
    """Local-knowledge submission (design doc §14).

    NEVER auto-published: rows start PENDING and become visible content only
    after an admin approves them (moderation writes an audit row). The MVP
    intake is the public endpoint; the Google Form flow feeds the same table.
    """

    __tablename__ = "community_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    submitter_name: Mapped[str] = mapped_column(String(120), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(160))  # email/phone, optional
    # Intake channel (§22): the Google Form import stamps GOOGLE_FORM (default);
    # the public API stamps IN_APP.
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="GOOGLE_FORM")
    # RITUAL | TRADITION | FOOD | CRAFT | FAIR_FESTIVAL | PLACE | HISTORY | EXPERIENCE | OTHER
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    state_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("states.id", ondelete="SET NULL")
    )
    city_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id", ondelete="SET NULL")
    )
    place_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    admin_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('RITUAL','TRADITION','FOOD','CRAFT','FAIR_FESTIVAL',"
            "'PLACE','HISTORY','EXPERIENCE','OTHER')",
            name="ck_community_suggestion_kind",
        ),
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED')",
            name="ck_community_suggestion_status",
        ),
    )
