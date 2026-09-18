"""Initial baseline (no tables yet).

Revision ID: 0001
Revises:
Create Date: 2026-09-17

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Phase 2 baseline: empty schema. Tables are added by dedicated revisions
    # in the auth/users phase, per docs/DATABASE_DESIGN.md.
    pass


def downgrade() -> None:
    pass
