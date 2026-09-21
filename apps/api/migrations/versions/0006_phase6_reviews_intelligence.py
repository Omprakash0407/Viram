"""Phase 6: place reviews + intelligence/safety tables (design doc §24, §27–§29).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "place_reviews",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("place_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("places.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(140), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("visited_on", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_place_reviews_rating_1_5"),
        sa.CheckConstraint("status IN ('PENDING','ACTIVE','HIDDEN')",
                           name="ck_place_reviews_status"),
        sa.UniqueConstraint("place_id", "author_id", name="uq_place_reviews_place_author"),
    )
    op.create_index("ix_place_reviews_place_created",
                    "place_reviews", ["place_id", sa.text("created_at DESC")])

    op.create_table(
        "weather_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("city_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("cities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("temperature_c", sa.Numeric(5, 1), nullable=False),
        sa.Column("condition", sa.String(60), nullable=False),
        sa.Column("humidity_pct", sa.Integer(), nullable=True),
        sa.Column("wind_kmph", sa.Numeric(5, 1), nullable=True),
        sa.Column("payload", pg.JSONB(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("city_id", "date", "provider", name="uq_weather_city_date_provider"),
        sa.CheckConstraint("temperature_c >= -90 AND temperature_c <= 60", name="ck_weather_temp"),
    )

    op.create_table(
        "route_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("origin_label", sa.String(160), nullable=False),
        sa.Column("origin_lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("origin_lng", sa.Numeric(9, 6), nullable=False),
        sa.Column("destination_label", sa.String(160), nullable=False),
        sa.Column("destination_lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("destination_lng", sa.Numeric(9, 6), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("distance_km", sa.Numeric(8, 2), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("polyline", sa.Text(), nullable=True),
        sa.Column("payload", pg.JSONB(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("distance_km >= 0", name="ck_route_distance_nonneg"),
        sa.CheckConstraint("duration_min >= 0", name="ck_route_duration_nonneg"),
    )

    op.create_table(
        "emergency_facilities",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("city_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("cities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("is_24x7", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.UniqueConstraint("city_id", "name", name="uq_emergency_facility_city_name"),
        sa.CheckConstraint(
            "kind IN ('HOSPITAL','CLINIC','PHARMACY','POLICE','FIRE_STATION','TOURIST_HELP')",
            name="ck_emergency_facility_kind",
        ),
    )
    op.create_index("ix_emergency_facilities_city", "emergency_facilities", ["city_id"])

    op.create_table(
        "community_suggestions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("submitter_name", sa.String(120), nullable=False),
        sa.Column("contact", sa.String(160), nullable=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("state_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("states.id", ondelete="SET NULL"), nullable=True),
        sa.Column("city_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("cities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("place_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("places.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", pg.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint(
            "kind IN ('RITUAL','TRADITION','FOOD','CRAFT','FAIR_FESTIVAL',"
            "'PLACE','HISTORY','EXPERIENCE','OTHER')",
            name="ck_community_suggestion_kind",
        ),
        sa.CheckConstraint("status IN ('PENDING','APPROVED','REJECTED')",
                           name="ck_community_suggestion_status"),
    )
    op.create_index("ix_community_suggestions_status",
                    "community_suggestions", ["status", "created_at"])

    op.create_table(
        "emergency_contacts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("state_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("states.id", ondelete="CASCADE"), nullable=True),
        sa.Column("city_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("cities.id", ondelete="CASCADE"), nullable=True),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.CheckConstraint("scope IN ('NATIONAL','STATE','CITY')",
                           name="ck_emergency_contact_scope"),
        sa.CheckConstraint(
            "(scope = 'NATIONAL' AND state_id IS NULL AND city_id IS NULL)"
            " OR (scope = 'STATE' AND state_id IS NOT NULL AND city_id IS NULL)"
            " OR (scope = 'CITY' AND city_id IS NOT NULL AND state_id IS NULL)",
            name="ck_emergency_contact_scope_shape",
        ),
    )


def downgrade() -> None:
    # IF EXISTS guards keep this downgrade safe even when applied over an
    # earlier shape of this same revision (e.g. an edited not-yet-shipped 0006).
    op.execute("DROP INDEX IF EXISTS ix_community_suggestions_status")
    op.execute("DROP TABLE IF EXISTS community_suggestions")
    op.drop_table("emergency_contacts")
    op.drop_index("ix_emergency_facilities_city", table_name="emergency_facilities")
    op.drop_table("emergency_facilities")
    op.drop_table("route_snapshots")
    op.drop_table("weather_snapshots")
    op.drop_index("ix_place_reviews_place_created", table_name="place_reviews")
    op.drop_table("place_reviews")
