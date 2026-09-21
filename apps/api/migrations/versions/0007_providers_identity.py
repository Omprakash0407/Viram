"""Phase 7: provider slice + identity verification (design doc §4, §5, §22).

- business_profiles: local businesses (Local Partners wall + discovery).
- identity_verifications: DigiLocker-style identity proofing. NO document
  number column exists by design — the Aadhaar number is never stored.
- community_suggestions.source: GOOGLE_FORM | IN_APP (§22 anticipated it).

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "business_profiles",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("state_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("states.id"), nullable=False),
        sa.Column("city_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("place_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("places.id"), nullable=True),
        sa.Column("services", pg.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("public_phone", sa.Text(), nullable=True),
        sa.Column("public_email", sa.Text(), nullable=True),
        sa.Column("public_address", sa.Text(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="PENDING"),
        sa.Column("visibility", sa.String(10), nullable=False, server_default="PRIVATE"),
        sa.Column("reviewed_by", pg.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','SUSPENDED')",
            name="ck_business_profiles_status",
        ),
        sa.CheckConstraint("visibility IN ('PUBLIC','PRIVATE')",
                           name="ck_business_profiles_visibility"),
        sa.CheckConstraint(
            "category IN ('CAFE','RESTAURANT','ARTISAN','HANDICRAFT','HOMESTAY',"
            "'FOOD','TOUR','EXPERIENCE','OTHER')",
            name="ck_business_profiles_category",
        ),
    )
    op.create_index("ix_business_profiles_owner", "business_profiles",
                    ["user_id", "created_at"])
    op.create_index("ix_business_profiles_city_public", "business_profiles", ["city_id"],
                    postgresql_where=sa.text("status = 'APPROVED' AND visibility = 'PUBLIC'"))
    op.create_index("ix_business_profiles_category_public", "business_profiles", ["category"],
                    postgresql_where=sa.text("status = 'APPROVED' AND visibility = 'PUBLIC'"))

    op.create_table(
        "identity_verifications",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False, server_default="DIGILOCKER_DEMO"),
        sa.Column("id_proof_type", sa.String(20), nullable=False, server_default="AADHAAR"),
        sa.Column("status", sa.String(12), nullable=False, server_default="PENDING"),
        sa.Column("provider_reference", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint(
            "provider IN ('DIGILOCKER_DEMO','DIGILOCKER','MANUAL_ADMIN')",
            name="ck_identity_verifications_provider",
        ),
        sa.CheckConstraint(
            "id_proof_type IN ('AADHAAR','DRIVING_LICENCE','VOTER_ID','PASSPORT')",
            name="ck_identity_verifications_proof_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','FAILED','EXPIRED')",
            name="ck_identity_verifications_status",
        ),
    )
    op.create_index("ix_identity_verifications_user_status", "identity_verifications",
                    ["user_id", "status"])

    # §22 anticipated in-app submission; the Google Form channel imports rows
    # with the default, the public API stamps IN_APP.
    op.add_column(
        "community_suggestions",
        sa.Column("source", sa.String(20), nullable=False, server_default="GOOGLE_FORM"),
    )
    op.create_check_constraint(
        "ck_community_suggestion_source", "community_suggestions",
        "source IN ('GOOGLE_FORM','IN_APP')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_community_suggestion_source", "community_suggestions")
    op.drop_column("community_suggestions", "source")
    op.drop_index("ix_identity_verifications_user_status", table_name="identity_verifications")
    op.drop_table("identity_verifications")
    op.drop_index("ix_business_profiles_category_public", table_name="business_profiles")
    op.drop_index("ix_business_profiles_city_public", table_name="business_profiles")
    op.drop_index("ix_business_profiles_owner", table_name="business_profiles")
    op.drop_table("business_profiles")
