"""auth domain: users, traveller_profiles, user_sessions, user_preferences

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-17

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("account_role", sa.String(length=10), nullable=False, server_default="USER"),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("account_role IN ('USER','ADMIN')", name="ck_users_account_role"),
        sa.CheckConstraint("status IN ('ACTIVE','DEACTIVATED')", name="ck_users_status"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "traveller_profiles",
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "user_sessions",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_user_sessions_refresh_token_hash",
        "user_sessions",
        ["refresh_token_hash"],
        unique=True,
    )
    op.create_index("ix_user_sessions_user_created", "user_sessions", ["user_id"])

    op.create_table(
        "user_preferences",
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("interests", pg.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("pace", sa.String(length=10), nullable=True),
        sa.Column("budget_level", sa.String(length=10), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.CheckConstraint("pace IN ('RELAXED','BALANCED','PACKED')", name="ck_user_pref_pace"),
        sa.CheckConstraint(
            "budget_level IN ('BUDGET','MID','PREMIUM')", name="ck_user_pref_budget"
        ),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_index("ix_user_sessions_user_created", table_name="user_sessions")
    op.drop_index("ix_user_sessions_refresh_token_hash", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_table("traveller_profiles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
