"""Weather + route endpoints (design doc §27–§28).

Weather reads go through the shared cache-or-fetch service so the REST API and
Vira AI tools behave identically; on provider failure the cache is served
as-is (stale-but-labelled) and a 503 only when no cached value exists.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import ValidationFailedError
from app.models.intelligence import RouteSnapshot
from app.modules.intelligence import providers, service

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/weather")
async def get_weather(
    city_id: uuid.UUID,
    date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cached weather for a city (+ optional ISO date); fetches on miss/TTL."""
    try:
        return await service.get_weather_cached(db, city_id=city_id, target_date=date)
    except service.WeatherUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/route")
async def get_route(
    o_label: str = Query(max_length=160),
    o_lat: float = Query(ge=-90, le=90),
    o_lng: float = Query(ge=-180, le=180),
    d_label: str = Query(max_length=160),
    d_lat: float = Query(ge=-90, le=90),
    d_lng: float = Query(ge=-180, le=180),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cached driving route between two labeled points; fetches on miss/TTL."""
    snap = (
        await db.scalar(
            select(RouteSnapshot).where(
                RouteSnapshot.origin_label == o_label,
                RouteSnapshot.destination_label == d_label,
                RouteSnapshot.provider == "osrm-demo",
            )
        )
    )
    fresh = (
        snap is not None
        and datetime.now(timezone.utc) - snap.retrieved_at
        < timedelta(minutes=providers.ROUTE_TTL_MINUTES)
    )
    if not fresh:
        try:
            data = await providers.fetch_route(o_label, o_lat, o_lng, d_label, d_lat, d_lng)
            if snap is None:
                snap = RouteSnapshot(
                    origin_label=o_label,
                    origin_lat=o_lat,
                    origin_lng=o_lng,
                    destination_label=d_label,
                    destination_lat=d_lat,
                    destination_lng=d_lng,
                    provider="osrm-demo",
                )
                db.add(snap)
            snap.distance_km = data["distance_km"]
            snap.duration_min = data["duration_min"]
            snap.retrieved_at = data["retrieved_at"]
            await db.commit()
            fresh = True  # just fetched — serve as fresh, not cached
        except Exception:
            if snap is None:
                raise HTTPException(
                    status_code=503,
                    detail="Routing provider unavailable and no cached snapshot exists.",
                )
            await db.rollback()

    return {
        "origin": {"label": snap.origin_label, "lat": float(snap.origin_lat), "lng": float(snap.origin_lng)},
        "destination": {"label": snap.destination_label, "lat": float(snap.destination_lat), "lng": float(snap.destination_lng)},
        "distance_km": float(snap.distance_km),
        "duration_min": snap.duration_min,
        "provider": snap.provider,
        "retrieved_at": snap.retrieved_at.isoformat(),
        "cached": not fresh,
    }
