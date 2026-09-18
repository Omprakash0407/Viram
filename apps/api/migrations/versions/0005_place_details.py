"""places.details JSONB — editorial detail payloads for place pages.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-18

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("places", sa.Column("details", pg.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("places", "details")
