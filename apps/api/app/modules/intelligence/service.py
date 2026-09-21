"""Intelligence service layer: shared weather resolution.

Extracted from the router so multiple callers (REST endpoint, Vira AI tools)
use the identical cache-or-fetch path with honest freshness labelling.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.geo import City
from app.models.intelligence import WeatherSnapshot
from app.modules.intelligence import providers


class WeatherUnavailableError(Exception):
    """Provider down and no cached snapshot exists."""


async def get_weather_cached(
    db: AsyncSession, *, city_id: uuid.UUID, target_date: str | None = None
) -> dict:
    """Cached weather for a city (+ optional ISO date); fetches on miss/TTL."""
    target = target_date or date_type.today().isoformat()
    try:
        date_type.fromisoformat(target)
    except ValueError as exc:
        raise ValidationFailedError("date must be ISO YYYY-MM-DD.") from exc

    city = await db.get(City, city_id)
    if city is None:
        raise NotFoundError("City not found.")

    snap = (
        await db.scalar(
            select(WeatherSnapshot).where(
                WeatherSnapshot.city_id == city.id,
                WeatherSnapshot.date == target,
                WeatherSnapshot.provider == "open-meteo",
            )
        )
    )
    fresh = (
        snap is not None
        and datetime.now(timezone.utc) - snap.retrieved_at
        < timedelta(minutes=providers.WEATHER_TTL_MINUTES)
    )
    if not fresh:
        try:
            data = await providers.fetch_weather(
                city.name, float(city.latitude), float(city.longitude), target
            )
            if snap is None:
                snap = WeatherSnapshot(city_id=city.id, date=target, provider="open-meteo")
                db.add(snap)
            snap.temperature_c = data["temperature_c"]
            snap.condition = data["condition"]
            snap.humidity_pct = data["humidity_pct"]
            snap.wind_kmph = data["wind_kmph"]
            snap.payload = {
                "tmax_c": data["tmax_c"],
                "tmin_c": data["tmin_c"],
            }
            snap.retrieved_at = data["retrieved_at"]
            await db.flush()
            fresh = True  # just fetched — serve as fresh, not cached
        except Exception:
            # provider down → serve cache if we have any, else honest failure
            if snap is None:
                raise WeatherUnavailableError(
                    "Weather provider unavailable and no cached snapshot exists."
                ) from None

    return {
        "city": {"id": str(city.id), "name": city.name},
        "date": target,
        "temperature_c": float(snap.temperature_c),
        "condition": snap.condition,
        "humidity_pct": snap.humidity_pct,
        "wind_kmph": float(snap.wind_kmph) if snap.wind_kmph is not None else None,
        "tmax_c": float(snap.payload["tmax_c"]) if snap.payload and snap.payload.get("tmax_c") is not None else None,
        "tmin_c": float(snap.payload["tmin_c"]) if snap.payload and snap.payload.get("tmin_c") is not None else None,
        "provider": snap.provider,
        "retrieved_at": snap.retrieved_at.isoformat(),
        "cached": not fresh,
    }
