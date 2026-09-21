"""Live location endpoints between companions of one trip (Phase 8b).

Mounted under /trips/{trip_id}/location. Every endpoint re-checks membership:
the caller must be the trip head or an ACTIVE companion of THAT trip. The
share row itself is the opt-in — POST creates/refreshes it, DELETE removes it
(stopping sharing instantly), GET returns the OTHER sharing companions only.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.modules.planning import location_service, sos_service
from app.modules.users.deps import get_current_user

router = APIRouter(tags=["live-location"])


class LocationPing(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: int | None = Field(default=None, ge=0, le=100_000)


@router.put("/trips/{trip_id}/location")
async def share_location(
    trip_id: uuid.UUID,
    payload: LocationPing,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Opt in / heartbeat. Creates or refreshes this traveller's share row."""
    trip = await location_service.active_trip_member(db, trip_id, user)
    if trip is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only companions of this trip can share location")
    row = await location_service.upsert_heartbeat(
        db,
        trip=trip,
        user=user,
        latitude=Decimal(str(payload.latitude)),
        longitude=Decimal(str(payload.longitude)),
        accuracy_m=payload.accuracy_m,
    )
    return {
        "sharing": True,
        "purge_date": row.purge_date.isoformat() if isinstance(row.purge_date, date) else str(row.purge_date),
    }


@router.delete("/trips/{trip_id}/location", status_code=status.HTTP_200_OK)
async def stop_location(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Opt out. The share row is deleted; companions stop seeing you immediately."""
    trip = await location_service.active_trip_member(db, trip_id, user)
    if trip is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only companions of this trip can manage location")
    existed = await location_service.stop_sharing(db, trip_id=trip_id, user=user)
    return {"sharing": False, "removed": existed}


@router.get("/trips/{trip_id}/location")
async def companion_locations(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Live positions of the OTHER sharing members of this trip (never your own)."""
    trip = await location_service.active_trip_member(db, trip_id, user)
    if trip is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only companions of this trip can see live locations")
    mine = await location_service.sharing_status(db, trip_id=trip_id, user=user)
    items = await location_service.trip_locations(db, trip=trip, viewer=user)
    return {"sharing": mine["sharing"], "items": items, "server_time": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}


@router.get("/trips/{trip_id}/sos")
async def trip_sos(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Safe-travel SOS: emergency contacts + facilities for the trip's city,
    and the fastest route from the freshest shared position to the nearest
    hospital. Same membership gate as live locations — trip members only."""
    trip = await location_service.active_trip_member(db, trip_id, user)
    if trip is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only companions of this trip can view SOS information")
    return await sos_service.sos_for_trip(db, trip=trip)


@router.post("/admin/purge-locations")
async def purge_locations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Maintenance sweep for expired retention windows (admin-only)."""
    if user.account_role != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    removed = await location_service.purge_expired(db)
    return {"purged": removed}
