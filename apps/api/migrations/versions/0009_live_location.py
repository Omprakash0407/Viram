"""Phase 8b: live location sharing between active companions of a trip.

companion_location_shares: an OPT-IN per (trip, user) heartbeat row. A row
only exists while the traveller is actively sharing; deleting it stops
sharing instantly. Points are never retained after the trip end date + 1 day
(purge_date) — live location is ephemeral, not historical data (§25's
preservation rule is for bookings/payments, not GPS pings).

Visibility rule: a traveller's position is readable ONLY by the trip head and
ACTIVE companions of the SAME trip, and only while that trip is ongoing.
TripCompanion's ACTIVE/HEAD status is the single source of truth — sharing
stops automatically the moment a companion is removed (row delete cascades
via the API, and reads re-check membership on every request).

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-21
"""


import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "companion_location_shares",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("trip_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("accuracy_m", sa.Integer()),
        sa.Column("purge_date", sa.Date(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_companion_location_shares"),
        sa.UniqueConstraint("trip_id", "user_id", name="uq_location_share_trip_user"),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_location_share_lat"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_location_share_lng"),
    )
    op.create_index("ix_location_shares_trip", "companion_location_shares", ["trip_id"])
    op.create_index("ix_location_shares_purge", "companion_location_shares", ["purge_date"])


def downgrade() -> None:
    op.drop_index("ix_location_shares_purge", table_name="companion_location_shares")
    op.drop_index("ix_location_shares_trip", table_name="companion_location_shares")
    op.drop_table("companion_location_shares")
