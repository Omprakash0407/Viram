"""geography + planning domain: states, cities, place_categories, places,
trips, itineraries, itinerary_days, itinerary_items, recommendation_runs,
recommendation_items

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-17

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "states",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.UniqueConstraint("name", name="states_name_key"),
        sa.UniqueConstraint("slug", name="states_slug_key"),
    )
    op.create_table(
        "cities",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("state_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.ForeignKeyConstraint(["state_id"], ["states.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("state_id", "name", name="uq_cities_state_name"),
        sa.UniqueConstraint("state_id", "slug", name="uq_cities_state_slug"),
    )
    op.create_table(
        "place_categories",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("name", name="place_categories_name_key"),
        sa.UniqueConstraint("slug", name="place_categories_slug_key"),
    )
    op.create_table(
        "places",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("city_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("classification", sa.String(length=20), nullable=False, server_default="POPULAR"),
        sa.Column("lesser_known_note", sa.Text(), nullable=True),
        sa.Column("popularity_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("rating_avg", sa.Numeric(2, 1), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("typical_visit_minutes", sa.Integer(), nullable=True),
        sa.Column("opening_hours", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["category_id"], ["place_categories.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("city_id", "slug", name="uq_places_city_slug"),
        sa.CheckConstraint(
            "classification IN ('POPULAR','LESSER_KNOWN')", name="ck_places_classification"
        ),
        sa.CheckConstraint(
            "classification <> 'LESSER_KNOWN' OR lesser_known_note IS NOT NULL",
            name="ck_places_lesser_known_note",
        ),
        sa.CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="ck_places_status"),
        sa.CheckConstraint("review_count >= 0", name="ck_places_review_count"),
    )
    op.create_index("ix_places_city", "places", ["city_id"])
    op.create_index("ix_places_category", "places", ["category_id"])

    op.create_table(
        "trips",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("city_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PLANNING"),
        sa.Column(
            "preferences_snapshot", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_trips_date_order"),
        sa.CheckConstraint(
            "status IN ('PLANNING','BOOKED','CONFIRMED','COMPLETED','CANCELLED')",
            name="ck_trips_status",
        ),
        sa.CheckConstraint("party_size BETWEEN 1 AND 50", name="ck_trips_party_size"),
    )
    op.create_index("ix_trips_user_created", "trips", ["user_id", "created_at"])

    op.create_table(
        "itineraries",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("trip_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("trip_id", name="uq_itineraries_trip"),
        sa.CheckConstraint("status IN ('ACTIVE','SUPERSEDED')", name="ck_itineraries_status"),
    )

    op.create_table(
        "itinerary_days",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("itinerary_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("day_number", sa.SmallInteger(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["itinerary_id"], ["itineraries.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("itinerary_id", "day_number", name="uq_itinerary_days_day_number"),
        sa.CheckConstraint("day_number >= 1", name="ck_itinerary_days_day_number"),
    )

    op.create_table(
        "recommendation_runs",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("trip_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("engine_name", sa.Text(), nullable=False, server_default="RuleBasedRecommendationEngine"),
        sa.Column("engine_version", sa.Text(), nullable=False),
        sa.Column("preference_snapshot", pg.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_recommendation_runs_user_created", "recommendation_runs", ["user_id", "created_at"]
    )
    op.create_index("ix_recommendation_runs_trip", "recommendation_runs", ["trip_id"])

    op.create_table(
        "recommendation_items",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("run_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("place_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(6, 2), nullable=True),
        sa.Column("classification", sa.String(length=20), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["recommendation_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
        sa.Index("ix_recommendation_items_run_rank", "run_id", "rank"),
        sa.CheckConstraint("rank >= 1", name="ck_recommendation_items_rank"),
        sa.CheckConstraint(
            "classification IN ('POPULAR','LESSER_KNOWN')",
            name="ck_recommendation_items_classification",
        ),
    )


    op.create_table(
        "itinerary_items",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("itinerary_day_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("place_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("custom_title", sa.Text(), nullable=True),
        sa.Column("recommendation_item_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["itinerary_day_id"], ["itinerary_days.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["recommendation_item_id"], ["recommendation_items.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("itinerary_day_id", "position", name="uq_itinerary_items_position"),
        sa.CheckConstraint("position >= 0", name="ck_itinerary_items_position"),
        sa.CheckConstraint(
            "place_id IS NOT NULL OR custom_title IS NOT NULL",
            name="ck_itinerary_items_reference",
        ),
        sa.CheckConstraint("duration_minutes > 0", name="ck_itinerary_items_duration"),
    )
    op.create_index("ix_itinerary_items_place", "itinerary_items", ["place_id"])


def downgrade() -> None:
    # exact reverse of upgrade: itinerary_items (FK -> recommendation_items) first
    op.drop_index("ix_itinerary_items_place", table_name="itinerary_items")
    op.drop_table("itinerary_items")
    op.drop_table("recommendation_items")
    op.drop_index("ix_recommendation_runs_trip", table_name="recommendation_runs")
    op.drop_index("ix_recommendation_runs_user_created", table_name="recommendation_runs")
    op.drop_table("recommendation_runs")
    op.drop_table("itinerary_days")
    op.drop_table("itineraries")
    op.drop_index("ix_trips_user_created", table_name="trips")
    op.drop_table("trips")
    op.drop_index("ix_places_category", table_name="places")
    op.drop_index("ix_places_city", table_name="places")
    op.drop_table("places")
    op.drop_table("place_categories")
    op.drop_table("cities")
    op.drop_table("states")
