"""Live location sharing between companions of one trip (Phase 8b).

Privacy contract (checked on EVERY call, never cached client-side):
- Sharing is OPT-IN per (trip, user): a heartbeat row exists only while the
  traveller shares; deleting it stops sharing instantly.
- Only ACTIVE companions and the trip HEAD may share or read on a trip, and
  only while the trip is ongoing (end date not passed).
- Reads return companions only — you never see strangers, and the responder
  never echoes your own position back to you.
- Stale heartbeats (> STALE_MINUTES old) are filtered out of reads: a closed
  browser must not keep appearing on the map.
- purge_date (trip end + 1 day) bounds retention; a maintenance sweep deletes
  expired rows. GPS points are ephemeral, not historical data.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.planning import CompanionLocationShare, Trip, TripCompanion
from app.models.user import User

STALE_MINUTES = 15  # heartbeats older than this are hidden from other viewers


def _purge_date_for(trip: Trip) -> date:
    """Keep points at most one day past the trip end (or 7 days for undated trips)."""
    end = getattr(trip, "ends_on", None)
    return (end + timedelta(days=1)) if end else (date.today() + timedelta(days=7))


async def active_trip_member(db: AsyncSession, trip_id: uuid.UUID, user: User) -> Trip | None:
    """The trip iff `user` is the head or an ACTIVE companion of it."""
    trip = await db.get(Trip, trip_id)
    if trip is None or trip.user_id != user.id:
        if trip is None:
            return None
        row = await db.scalar(
            select(TripCompanion).where(
                TripCompanion.trip_id == trip_id,
                TripCompanion.companion_user_id == user.id,
                TripCompanion.status == "ACTIVE",
            )
        )
        if row is None:
            return None
    return trip


async def upsert_heartbeat(
    db: AsyncSession,
    *,
    trip: Trip,
    user: User,
    latitude: Decimal,
    longitude: Decimal,
    accuracy_m: int | None,
) -> CompanionLocationShare:
    """Create or refresh this traveller's share row (one row per trip+user)."""
    row = await db.scalar(
        select(CompanionLocationShare).where(
            CompanionLocationShare.trip_id == trip.id,
            CompanionLocationShare.user_id == user.id,
        )
    )
    if row is None:
        row = CompanionLocationShare(
            trip_id=trip.id, user_id=user.id, latitude=latitude, longitude=longitude,
            accuracy_m=accuracy_m, purge_date=_purge_date_for(trip),
        )
        db.add(row)
    else:
        row.latitude = latitude
        row.longitude = longitude
        row.accuracy_m = accuracy_m
        row.purge_date = _purge_date_for(trip)
    await db.commit()
    await db.refresh(row)
    return row


async def stop_sharing(db: AsyncSession, *, trip_id: uuid.UUID, user: User) -> bool:
    """Delete the share row; returns whether one existed."""
    result = await db.execute(
        delete(CompanionLocationShare).where(
            CompanionLocationShare.trip_id == trip_id,
            CompanionLocationShare.user_id == user.id,
        )
    )
    await db.commit()
    return (result.rowcount or 0) > 0


async def sharing_status(db: AsyncSession, *, trip_id: uuid.UUID, user: User) -> dict:
    """Whether `user` is currently sharing on this trip (their own row, unfiltered)."""
    row = await db.scalar(
        select(CompanionLocationShare).where(
            CompanionLocationShare.trip_id == trip_id,
            CompanionLocationShare.user_id == user.id,
        )
    )
    return {"sharing": row is not None}


async def trip_locations(
    db: AsyncSession, *, trip: Trip, viewer: User
) -> list[dict]:
    """Live positions of OTHER sharing members of this trip, freshest first.

    Caller has already verified `viewer` is the head or an ACTIVE companion.
    Stale heartbeats are dropped; the viewer never sees their own row here.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_MINUTES)
    rows = (
        await db.scalars(
            select(CompanionLocationShare)
            .where(
                CompanionLocationShare.trip_id == trip.id,
                CompanionLocationShare.updated_at >= cutoff,
            )
            .order_by(CompanionLocationShare.updated_at.desc())
        )
    ).all()
    out: list[dict] = []
    for row in rows:
        if row.user_id == viewer.id:
            continue  # never echo the viewer's own position back
        member = await db.get(User, row.user_id)
        if member is None:
            continue
        out.append(
            {
                "user_id": str(row.user_id),
                "display_name": member.display_name,
                "avatar_url": getattr(member, "avatar_url", None),
                "latitude": float(row.latitude),
                "longitude": float(row.longitude),
                "accuracy_m": row.accuracy_m,
                "updated_at": row.updated_at.isoformat(),
                "stale": False,
            }
        )
    return out


async def purge_expired(db: AsyncSession) -> int:
    """Maintenance sweep: delete shares whose retention window has passed."""
    result = await db.execute(
        delete(CompanionLocationShare).where(CompanionLocationShare.purge_date < date.today())
    )
    await db.commit()
    return result.rowcount or 0
