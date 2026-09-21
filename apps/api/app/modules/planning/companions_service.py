"""Companionship business logic (Phase 8a "travelling together").

Invite lifecycle and access rules live here; the routers stay thin.
Self-invite, duplicate invites and non-head invites are rejected.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.exceptions import ConflictError, ValidationError
from app.models.planning import Trip, TripCompanion
from app.models.user import User, TravellerProfile


async def _trip_or_404(db: AsyncSession, trip_id: uuid.UUID) -> Trip:
    trip = await db.get(Trip, trip_id)
    if trip is None:
        raise NotFoundError("Trip not found.")
    return trip


async def invite(
    db: AsyncSession, *, user: User, trip_id: uuid.UUID, email: str
) -> TripCompanion:
    trip = await _trip_or_404(db, trip_id)
    if trip.user_id != user.id:
        raise PermissionDeniedError("Only the trip head can invite companions.")

    email_norm = email.strip().lower()
    companion = (
        await db.scalars(select(User).where(User.email == email_norm))
    ).first()
    if companion is None:
        # Do not reveal whether an account exists (account-enumeration guard).
        raise ValidationError("No VIRĀM account found for that email yet.")
    if companion.id == user.id:
        raise ValidationError("You are already the head of this trip.")

    existing = (
        await db.scalars(
            select(TripCompanion).where(
                TripCompanion.trip_id == trip.id,
                TripCompanion.companion_user_id == companion.id,
            )
        )
    ).first()
    if existing is not None:
        if existing.status in ("INVITED", "ACTIVE"):
            raise ConflictError("That person is already invited or on this trip.")
        # DECLINED/REMOVED rows are re-invited in place, preserving history.
        existing.status = "INVITED"
        existing.invited_by = user.id
        existing.responded_at = None
        await db.flush()
        return existing

    row = TripCompanion(
        trip_id=trip.id,
        invited_by=user.id,
        companion_user_id=companion.id,
        role="MEMBER",
        status="INVITED",
    )
    db.add(row)
    await db.flush()
    return row


async def remove(
    db: AsyncSession, *, user: User, trip_id: uuid.UUID, row_id: uuid.UUID
) -> None:
    trip = await _trip_or_404(db, trip_id)
    if trip.user_id != user.id:
        raise PermissionDeniedError("Only the trip head can remove companions.")
    row = await db.get(TripCompanion, row_id)
    if row is None or row.trip_id != trip.id:
        raise NotFoundError("Invitation not found for this trip.")
    row.status = "REMOVED"
    row.responded_at = func_now()
    await db.flush()


def func_now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


async def respond(
    db: AsyncSession, *, user: User, row_id: uuid.UUID, accept: bool
) -> dict:
    row = await db.get(TripCompanion, row_id)
    if row is None:
        raise NotFoundError("Invitation not found.")
    if row.companion_user_id != user.id:
        raise PermissionDeniedError("Not your invitation.")
    if row.status != "INVITED":
        raise ConflictError("This invitation was already answered or withdrawn.")

    row.status = "ACTIVE" if accept else "DECLINED"
    row.responded_at = func_now()
    await db.flush()
    return {"id": str(row.id), "status": row.status, "trip_id": str(row.trip_id)}


async def list_for_trip(
    db: AsyncSession, *, user: User, trip_id: uuid.UUID
) -> list[dict]:
    trip = await _trip_or_404(db, trip_id)
    if trip.user_id != user.id:
        raise PermissionDeniedError("Only the trip head can view the companion list.")
    rows = (
        await db.scalars(
            select(TripCompanion)
            .where(TripCompanion.trip_id == trip.id)
            .order_by(TripCompanion.invited_at.desc())
        )
    ).all()
    out: list[dict] = []
    for r in rows:
        u = await db.get(User, r.companion_user_id)
        prof = await db.get(TravellerProfile, r.companion_user_id)
        out.append(
            {
                "id": str(r.id),
                "companion_user_id": str(r.companion_user_id),
                "name": (u.display_name if u else "Traveller"),
                "avatar_url": (prof.avatar_url if prof else None),
                "status": r.status,
                "invited_at": r.invited_at.isoformat(),
            }
        )
    return out


async def invitations_for(db: AsyncSession, *, user: User) -> list[dict]:
    rows = (
        await db.scalars(
            select(TripCompanion).where(
                TripCompanion.companion_user_id == user.id,
                TripCompanion.status == "INVITED",
            )
        )
    ).all()
    out: list[dict] = []
    for r in rows:
        trip = await db.get(Trip, r.trip_id)
        head = await db.get(User, r.invited_by)
        out.append(
            {
                "id": str(r.id),
                "trip_id": str(r.trip_id),
                "city_id": str(trip.city_id) if trip else None,
                "starts_on": trip.starts_on.isoformat() if trip else None,
                "ends_on": trip.ends_on.isoformat() if trip else None,
                "invited_by_name": head.display_name if head else "A traveller",
            }
        )
    return out


async def is_active_companion(
    db: AsyncSession, *, trip_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    row = (
        await db.scalars(
            select(TripCompanion).where(
                TripCompanion.trip_id == trip_id,
                TripCompanion.companion_user_id == user_id,
                TripCompanion.status == "ACTIVE",
            )
        )
    ).first()
    return row is not None


async def shared_trips_for(db: AsyncSession, *, user: User) -> list[dict]:
    """Trips this user follows as an accepted companion (for the trips page)."""
    rows = (
        await db.scalars(
            select(TripCompanion).where(
                TripCompanion.companion_user_id == user.id,
                TripCompanion.status == "ACTIVE",
            )
        )
    ).all()
    out: list[dict] = []
    for r in rows:
        trip = await db.get(Trip, r.trip_id)
        if trip is None:
            continue
        head = await db.get(User, trip.user_id)
        out.append(
            {
                "trip_id": str(trip.id),
                "status": trip.status,
                "starts_on": trip.starts_on.isoformat(),
                "ends_on": trip.ends_on.isoformat(),
                "party_size": trip.party_size,
                "head_name": head.display_name if head else "Traveller",
            }
        )
    return out
