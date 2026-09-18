"""ORM models: auth domain. Source of truth: docs/DATABASE_DESIGN.md.

Status columns use text + CHECK constraints, not native ENUMs (decision D16).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def pk_uuid():
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


def ts(onupdate=None):
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=onupdate
    )


class AccountRole(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DEACTIVATED = "DEACTIVATED"


class User(Base):
    """§1 - account root. account_role is the only account-level distinction."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = pk_uuid()
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_role: Mapped[str] = mapped_column(
        String(10), nullable=False, default="USER", server_default="USER"
    )
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    created_at: Mapped[datetime] = ts()
    updated_at: Mapped[datetime] = ts(onupdate=func.now())

    __table_args__ = (
        CheckConstraint("account_role IN ('USER','ADMIN')", name="ck_users_account_role"),
        CheckConstraint("status IN ('ACTIVE','DEACTIVATED')", name="ck_users_status"),
    )

    traveller_profile: Mapped["TravellerProfile"] = relationship(
        back_populates="user", uselist=False
    )
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")
    preferences: Mapped["UserPreference"] = relationship(
        back_populates="user", uselist=False
    )


class TravellerProfile(Base):
    """§1.3 - the default profile, 1:1, auto-created at registration."""

    __tablename__ = "traveller_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    full_name: Mapped[str | None] = mapped_column(String(120))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(20))
    # home_state_id joins states - added by the geography migration (Phase 4).
    bio: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = ts(onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="traveller_profile")


class UserSession(Base):
    """§1.2 - revocable refresh sessions; raw tokens never stored, only hashes."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = pk_uuid()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = ts()

    __table_args__ = (Index("ix_user_sessions_user_created", "user_id"),)

    user: Mapped["User"] = relationship("User", back_populates="sessions")


class UserPreference(Base):
    """§10 - persistent traveller preferences (1:1)."""

    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    interests: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    pace: Mapped[str | None] = mapped_column(String(10))
    budget_level: Mapped[str | None] = mapped_column(String(10))
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = ts(onupdate=func.now())

    __table_args__ = (
        CheckConstraint("pace IN ('RELAXED','BALANCED','PACKED')", name="ck_user_pref_pace"),
        CheckConstraint(
            "budget_level IN ('BUDGET','MID','PREMIUM')", name="ck_user_pref_budget"
        ),
    )

    user: Mapped["User"] = relationship(back_populates="preferences")
