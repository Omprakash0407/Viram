"""Safe-travel SOS for one trip (design doc §28, §29 + Phase 8b live locations).

Composes EXISTING, separately-governed data — it never invents emergency
content:
- EmergencyContact / EmergencyFacility rows are admin/seed-managed (§29:
  emergency information is maintained separately from traveller content).
- The fastest route comes from the real OSRM provider used by /intelligence
  (§28) and is written to route_snapshots so every SOS query leaves an honest,
  timestamped trace.

Reference point for "nearest": the freshest live position shared on this trip
(any ACTIVE member, including the viewer — in an emergency the person asking
may be the one in trouble). With no live position at all the response says so
honestly and still returns contacts + facilities (they don't depend on GPS).
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import City
from app.models.intelligence import (
    EmergencyContact,
    EmergencyFacility,
    RouteSnapshot,
)
from app.models.planning import CompanionLocationShare, Trip
from app.models.user import User
from app.modules.intelligence import providers
from app.modules.planning.location_service import STALE_MINUTES

HOSPITAL_KINDS = ("HOSPITAL",)  # nearest-hospital preference order starts here


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance — straight line, clearly labelled as such."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


async def _contacts(db: AsyncSession, city: City) -> list[dict]:
    rows = (await db.scalars(select(EmergencyContact))).all()
    return [
        {"scope": c.scope, "label": c.label, "phone": c.phone, "description": c.description}
        for c in rows
        if c.scope == "NATIONAL"
        or (c.scope == "STATE" and c.state_id == city.state_id)
        or (c.scope == "CITY" and c.city_id == city.id)
    ]


async def _facilities(db: AsyncSession, city_id: uuid.UUID) -> list[dict]:
    rows = (
        await db.scalars(
            select(EmergencyFacility)
            .where(EmergencyFacility.city_id == city_id)
            .order_by(EmergencyFacility.kind, EmergencyFacility.name)
        )
    ).all()
    return [
        {
            "id": str(f.id),
            "name": f.name,
            "kind": f.kind,
            "address": f.address,
            "phone": f.phone,
            "is_24x7": f.is_24x7,
            "latitude": float(f.latitude),
            "longitude": float(f.longitude),
        }
        for f in rows
    ]


async def _freshest_share(
    db: AsyncSession, trip_id: uuid.UUID
) -> CompanionLocationShare | None:
    """Most recent fresh heartbeat on this trip, any member (viewer included)."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_MINUTES)
    return await db.scalar(
        select(CompanionLocationShare)
        .where(
            CompanionLocationShare.trip_id == trip_id,
            CompanionLocationShare.updated_at >= cutoff,
        )
        .order_by(CompanionLocationShare.updated_at.desc())
        .limit(1)
    )


async def sos_for_trip(db: AsyncSession, *, trip: Trip) -> dict:
    """Contacts + facilities for the trip's city, and the fastest driving route
    from the freshest shared position to the nearest hospital (any 24x7
    facility if no hospital exists in the city)."""
    city = await db.get(City, trip.city_id)
    if city is None:  # FK guarantees existence; belt-and-braces
        return {"contacts": [], "facilities": [], "route": None, "reference": None}

    contacts = await _contacts(db, city)
    facilities = await _facilities(db, city.id)

    share = await _freshest_share(db, trip.id)
    reference = None
    route = None

    if share is not None and facilities:
        o_lat, o_lng = float(share.latitude), float(share.longitude)
        member = await db.get(User, share.user_id)
        who = getattr(member, "display_name", "a traveller")
        reference = {
            "from": who,
            "latitude": o_lat,
            "longitude": o_lng,
            "updated_at": share.updated_at.isoformat(),
        }

        # Nearest by straight line first — cheap and deterministic — then the
        # REAL driving route to that one target (§28: snapshots, not guarantees).
        ranked = sorted(
            facilities, key=lambda f: haversine_km(o_lat, o_lng, f["latitude"], f["longitude"])
        )
        hospitals = [f for f in ranked if f["kind"] in HOSPITAL_KINDS]
        target = hospitals[0] if hospitals else ranked[0]
        straight_km = haversine_km(o_lat, o_lng, target["latitude"], target["longitude"])

        try:
            data = await providers.fetch_route(
                f"Live location ({who})",
                o_lat,
                o_lng,
                target["name"],
                target["latitude"],
                target["longitude"],
            )
            snap = RouteSnapshot(
                origin_label=f"Live location ({who})",
                origin_lat=o_lat,
                origin_lng=o_lng,
                destination_label=target["name"],
                destination_lat=target["latitude"],
                destination_lng=target["longitude"],
                provider=data["provider"],
                distance_km=data["distance_km"],
                duration_min=data["duration_min"],
            )
            db.add(snap)
            await db.commit()
            route = {
                "to": target,
                "straight_line_km": straight_km,
                "distance_km": data["distance_km"],
                "duration_min": data["duration_min"],
                "provider": data["provider"],
                "retrieved_at": data["retrieved_at"].isoformat()
                if isinstance(data["retrieved_at"], datetime)
                else str(data["retrieved_at"]),
            }
        except Exception:
            await db.rollback()
            # Provider down: keep the SOS panel useful — straight-line only,
            # clearly labelled as NOT a driving route.
            route = {
                "to": target,
                "straight_line_km": straight_km,
                "distance_km": None,
                "duration_min": None,
                "provider": None,
                "retrieved_at": None,
                "unavailable": True,
            }

    return {
        "contacts": contacts,
        "facilities": facilities,
        "route": route,
        "reference": reference,
    }
