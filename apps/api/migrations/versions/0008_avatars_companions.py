"""Phase 8a: avatars + travelling-together companions.

- traveller_profiles.avatar_url already existed (schema §1.3); this migration
  only adds the sharing primitive.
- trip_companions: the trip head (trips.user_id) invites other VIRĀM accounts
  to follow a trip. Companions get read-only access to the shared itinerary —
  never to the head's bookings or payments (§24 OWNER_ONLY stays intact;
  sharing is an explicit, revocable grant, not a visibility level).

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None

STATUS_CHECK = "status IN ('INVITED','ACTIVE','DECLINED','REMOVED')"


def upgrade() -> None:
    op.create_table(
        "trip_companions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("trip_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_by", pg.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("companion_user_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="MEMBER"),
        sa.Column("status", sa.String(10), nullable=False, server_default="INVITED"),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('HEAD','MEMBER')", name="ck_trip_companions_role"),
        sa.CheckConstraint(STATUS_CHECK, name="ck_trip_companions_status"),
        sa.UniqueConstraint("trip_id", "companion_user_id",
                            name="uq_trip_companions_trip_user"),
    )
    op.create_index("ix_trip_companions_companion", "trip_companions",
                    ["companion_user_id", "status"])
    op.create_index("ix_trip_companions_trip", "trip_companions", ["trip_id"])


def downgrade() -> None:
    op.drop_index("ix_trip_companions_trip", table_name="trip_companions")
    op.drop_index("ix_trip_companions_companion", table_name="trip_companions")
    op.drop_table("trip_companions")
