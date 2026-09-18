"""commerce domain: hotels, room_types, hotel_bookings, guide_profiles,
guide_availability, guide_bookings, payments, refunds, payment_webhook_events,
admin_audit_log

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-18

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # hotels: admin-managed in MVP, no owner (D7)
    op.create_table(
        "hotels",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("city_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column(
            "amenities",
            pg.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column("public_phone", sa.Text(), nullable=True),
        sa.Column("public_email", sa.Text(), nullable=True),
        sa.Column("public_address", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("city_id", "slug", name="uq_hotels_city_slug"),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_hotels_status"),
    )

    op.create_table(
        "room_types",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("hotel_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("nightly_rate_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False, server_default="INR"),
        sa.Column("declared_units", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotels.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("hotel_id", "name", name="uq_room_types_hotel_name"),
        sa.CheckConstraint("capacity BETWEEN 1 AND 10", name="ck_room_types_capacity"),
        sa.CheckConstraint("nightly_rate_paise > 0", name="ck_room_types_rate"),
    )

    op.create_table(
        "hotel_bookings",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("reference_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("trip_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("hotel_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("room_type_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("check_in_date", sa.Date(), nullable=False),
        sa.Column("check_out_date", sa.Date(), nullable=False),
        sa.Column("rooms_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("price_snapshot_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False, server_default="INR"),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="PENDING_PAYMENT"
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotels.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["room_type_id"], ["room_types.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("check_out_date > check_in_date", name="ck_hotel_bookings_dates"),
        sa.CheckConstraint(
            "status IN ('PENDING_PAYMENT','CONFIRMED','CANCELLED','COMPLETED','REFUNDED')",
            name="ck_hotel_bookings_status",
        ),
        sa.CheckConstraint("rooms_count >= 1", name="ck_hotel_bookings_rooms"),
        sa.CheckConstraint("price_snapshot_paise > 0", name="ck_hotel_bookings_price"),
    )
    op.create_index("ix_hotel_bookings_user_created", "hotel_bookings", ["user_id", "created_at"])
    op.create_index(
        "ix_hotel_bookings_status_checkin", "hotel_bookings", ["status", "check_in_date"]
    )

    op.create_table(
        "guide_profiles",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("public_name", sa.String(length=200), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column(
            "languages", pg.ARRAY(sa.Text()), nullable=False, server_default=sa.text("ARRAY[]::text[]")
        ),
        sa.Column(
            "expertise", pg.ARRAY(sa.Text()), nullable=False, server_default=sa.text("ARRAY[]::text[]")
        ),
        sa.Column(
            "areas_served",
            pg.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column("city_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("day_rate_paise", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.CHAR(length=3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="PENDING"),
        sa.Column("visibility", sa.String(length=10), nullable=False, server_default="PRIVATE"),
        sa.Column("reviewed_by", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", name="uq_guide_profiles_user"),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','SUSPENDED')",
            name="ck_guide_profiles_status",
        ),
        sa.CheckConstraint("visibility IN ('PUBLIC','PRIVATE')", name="ck_guide_profiles_visibility"),
        sa.CheckConstraint(
            "day_rate_paise IS NULL OR day_rate_paise > 0", name="ck_guide_profiles_rate"
        ),
    )
    op.create_index(
        "ix_guide_profiles_city_public",
        "guide_profiles",
        ["city_id"],
        postgresql_where=sa.text("status = 'APPROVED' AND visibility = 'PUBLIC'"),
    )

    op.create_table(
        "guide_availability",
        sa.Column("guide_profile_id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("service_date", sa.Date(), primary_key=True),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="AVAILABLE"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["guide_profile_id"], ["guide_profiles.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "status IN ('AVAILABLE','UNAVAILABLE','BUSY')", name="ck_guide_availability_status"
        ),
    )
    op.create_index(
        "ix_guide_availability_service_date", "guide_availability", ["service_date"]
    )

    op.create_table(
        "guide_bookings",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("reference_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("trip_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("guide_profile_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("service_start_date", sa.Date(), nullable=False),
        sa.Column("service_end_date", sa.Date(), nullable=False),
        sa.Column("price_snapshot_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False, server_default="INR"),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="PENDING_PAYMENT"
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["guide_profile_id"], ["guide_profiles.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "service_end_date >= service_start_date", name="ck_guide_bookings_dates"
        ),
        sa.CheckConstraint(
            "status IN ('PENDING_PAYMENT','CONFIRMED','CANCELLED','COMPLETED','REFUNDED')",
            name="ck_guide_bookings_status",
        ),
        sa.CheckConstraint("price_snapshot_paise > 0", name="ck_guide_bookings_price"),
    )
    op.create_index("ix_guide_bookings_user_created", "guide_bookings", ["user_id", "created_at"])
    op.create_index(
        "ix_guide_bookings_guide_status_start",
        "guide_bookings",
        ["guide_profile_id", "status", "service_start_date"],
    )
    op.create_index(
        "ix_guide_bookings_status_start", "guide_bookings", ["status", "service_start_date"]
    )

    op.create_table(
        "payments",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("hotel_booking_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("guide_booking_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("gateway", sa.String(length=40), nullable=False),
        sa.Column("gateway_order_id", sa.Text(), nullable=False),
        sa.Column("gateway_payment_id", sa.Text(), nullable=True),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="CREATED"),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["hotel_booking_id"], ["hotel_bookings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["guide_booking_id"], ["guide_bookings.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "hotel_booking_id IS NOT NULL OR guide_booking_id IS NOT NULL",
            name="ck_payments_booking_link",
        ),
        sa.CheckConstraint("amount_paise > 0", name="ck_payments_amount"),
        sa.CheckConstraint(
            "status IN ('CREATED','PENDING','SUCCEEDED','FAILED','REFUNDED')",
            name="ck_payments_status",
        ),
        sa.UniqueConstraint("gateway_order_id", name="uq_payments_gateway_order"),
        sa.UniqueConstraint("gateway_payment_id", name="uq_payments_gateway_payment"),
        sa.UniqueConstraint("idempotency_key", name="uq_payments_idempotency"),
    )
    op.create_index("ix_payments_user_created", "payments", ["user_id", "created_at"])

    op.create_table(
        "refunds",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("payment_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False, server_default="INR"),
        sa.Column("gateway_refund_id", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="REQUESTED"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("amount_paise > 0", name="ck_refunds_amount"),
        sa.CheckConstraint(
            "status IN ('REQUESTED','PROCESSING','PROCESSED','FAILED')", name="ck_refunds_status"
        ),
        sa.UniqueConstraint("gateway_refund_id", name="uq_refunds_gateway_refund"),
    )

    op.create_table(
        "payment_webhook_events",
        sa.Column("provider", sa.String(length=40), primary_key=True),
        sa.Column("event_id", sa.String(length=200), primary_key=True),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "admin_audit_log",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("admin_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=60), nullable=False),
        sa.Column("target_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("before", pg.JSONB(), nullable=True),
        sa.Column("after", pg.JSONB(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_admin_audit_log_target", "admin_audit_log", ["target_type", "target_id"])
    op.create_index("ix_admin_audit_log_created", "admin_audit_log", ["created_at"])


def downgrade() -> None:
    # exact reverse of upgrade; financial history dies with these tables in dev only
    op.drop_index("ix_admin_audit_log_created", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_target", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
    op.drop_table("payment_webhook_events")
    op.drop_table("refunds")
    op.drop_index("ix_payments_user_created", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_guide_bookings_status_start", table_name="guide_bookings")
    op.drop_index("ix_guide_bookings_guide_status_start", table_name="guide_bookings")
    op.drop_index("ix_guide_bookings_user_created", table_name="guide_bookings")
    op.drop_table("guide_bookings")
    op.drop_index("ix_guide_availability_service_date", table_name="guide_availability")
    op.drop_table("guide_availability")
    op.drop_index("ix_guide_profiles_city_public", table_name="guide_profiles")
    op.drop_table("guide_profiles")
    op.drop_index("ix_hotel_bookings_status_checkin", table_name="hotel_bookings")
    op.drop_index("ix_hotel_bookings_user_created", table_name="hotel_bookings")
    op.drop_table("hotel_bookings")
    op.drop_table("room_types")
    op.drop_table("hotels")
