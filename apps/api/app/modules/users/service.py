"""Auth service: registration, login, refresh rotation, logout.

Business rules (design doc §1):
- Registration creates users + traveller_profiles atomically (decision D1/D3).
- Refresh tokens are opaque, stored as sha-256 hashes bound to revocable sessions.
- Refresh rotates: the used token is revoked and a new one issued.
- Login/refresh are refused for non-ACTIVE accounts.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError as NotFoundError404
from app.core.exceptions import (
    AccountDisabledError,
    ConflictError,
    InvalidCredentialsError,
    RefreshTokenInvalidError,
)
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.user import TravellerProfile, User, UserPreference, UserSession


def _access_token(user: User) -> str:
    return create_access_token(user.id, user.account_role)


def _new_session_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


async def _issue_session(db: AsyncSession, user: User) -> str:
    raw, token_hash = generate_refresh_token()
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=token_hash,
        expires_at=_new_session_expiry(),
    )
    db.add(session)
    await db.flush()
    return raw


async def register(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str,
) -> User:
    """Create account + traveller profile atomically; raises ConflictError on duplicate."""
    email = email.strip().lower()
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise ConflictError("An account with this email already exists.")

    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name.strip(),
        account_role="USER",
        status="ACTIVE",
    )
    db.add(user)
    await db.flush()  # assign user.id before creating the profile

    db.add(TravellerProfile(user_id=user.id, full_name=display_name.strip()))
    return user


async def authenticate(db: AsyncSession, *, email: str, password: str) -> User:
    """Verify credentials; raises InvalidCredentialsError on any mismatch."""
    email = email.strip().lower()
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        # Same error and timing-profile as the wrong-password path.
        verify_password(password, _dummy_hash_value())
        raise InvalidCredentialsError("Invalid email or password.")
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid email or password.")
    if user.status != "ACTIVE":
        raise AccountDisabledError("This account has been deactivated.")
    return user


async def login(db: AsyncSession, *, email: str, password: str) -> dict:
    user = await authenticate(db, email=email, password=password)
    access = _access_token(user)
    refresh = await _issue_session(db, user)
    return {"user": user, "access_token": access, "refresh_token": refresh}


async def issue_tokens(db: AsyncSession, user: User) -> dict:
    """Issue a fresh token pair for an already-persisted user (register flow)."""
    access = _access_token(user)
    refresh = await _issue_session(db, user)
    return {"user": user, "access_token": access, "refresh_token": refresh}


async def get_profile(db: AsyncSession, *, user_id: uuid.UUID):
    profile = await db.get(TravellerProfile, user_id)
    if profile is None:
        raise NotFoundError404("Profile not found.")
    return profile


async def update_profile(db: AsyncSession, *, user_id: uuid.UUID, data: dict):
    profile = await db.get(TravellerProfile, user_id)
    if profile is None:
        raise NotFoundError404("Profile not found.")
    for field, value in data.items():
        setattr(profile, field, value)
    await db.flush()
    return profile


async def get_or_create_preferences(db: AsyncSession, *, user_id: uuid.UUID):
    prefs = await db.get(UserPreference, user_id)
    if prefs is None:
        prefs = UserPreference(user_id=user_id, interests=[])
        db.add(prefs)
        await db.flush()
    return prefs


async def update_preferences(db: AsyncSession, *, user_id: uuid.UUID, data: dict):
    prefs = await get_or_create_preferences(db, user_id=user_id)
    for field, value in data.items():
        setattr(prefs, field, value)
    await db.flush()
    return prefs


async def refresh(db: AsyncSession, *, raw_refresh_token: str) -> dict:
    """Rotate the session: revoke the used token, issue a fresh pair."""
    token_hash = hash_refresh_token(raw_refresh_token)
    session = await db.scalar(select(UserSession).where(UserSession.refresh_token_hash == token_hash))

    valid = (
        session is not None
        and session.revoked_at is None
        and session.expires_at > datetime.now(timezone.utc)
    )
    if not valid:
        raise RefreshTokenInvalidError("Invalid or expired refresh token.")

    user = await db.scalar(select(User).where(User.id == session.user_id))
    if user is None or user.status != "ACTIVE":
        raise RefreshTokenInvalidError("Invalid or expired refresh token.")

    session.revoked_at = _utcnow()
    await db.flush()
    access = _access_token(user)
    new_refresh = await _issue_session(db, user)
    return {"user": user, "access_token": access, "refresh_token": new_refresh}


async def revoke_session(db: AsyncSession, *, raw_refresh_token: str) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    await db.execute(
        update(UserSession)
        .where(UserSession.refresh_token_hash == token_hash, UserSession.revoked_at.is_(None))
        .values(revoked_at=_utcnow())
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_dummy_hash: str | None = None


def _dummy_hash_value() -> str:
    """Lazily computed argon2 hash used only for timing equalization."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("timing-equalization-only")
    return _dummy_hash
