"""External intelligence providers — real, key-less, and honestly cached.

- Weather: Open-Meteo (https://open-meteo.com), free, no API key.
- Routes: OSRM public demo server (https://project-osrm.org), free, no key.

Snapshots are cached in Postgres and re-read at most once per TTL; if a
provider is unreachable the cached snapshot is served with its original
retrieval timestamp — the API never fabricates data or presents a stale
cache as live.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

WEATHER_TTL_MINUTES = 60
ROUTE_TTL_MINUTES = 60


async def fetch_weather(city_name: str, lat: float, lng: float, date_iso: str) -> dict:
    """Current + daily forecast fields for the given coordinate/date."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lng}"
        "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
        "&daily=temperature_2m_max,temperature_2m_min,weather_code"
        f"&start_date={date_iso}&end_date={date_iso}"
        "&timezone=auto"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(url)
        res.raise_for_status()
        data = res.json()

    current = data.get("current") or {}
    daily = (data.get("daily") or {})
    tmax = (daily.get("temperature_2m_max") or [None])[0]
    tmin = (daily.get("temperature_2m_min") or [None])[0]
    return {
        "temperature_c": current.get("temperature_2m", tmin),
        "condition": _weather_text(current.get("weather_code")),
        "humidity_pct": current.get("relative_humidity_2m"),
        "wind_kmph": current.get("wind_speed_10m"),
        "tmax_c": tmax,
        "tmin_c": tmin,
        "provider": "open-meteo",
        "retrieved_at": datetime.now(timezone.utc),
    }


async def fetch_route(
    o_label: str, o_lat: float, o_lng: float, d_label: str, d_lat: float, d_lng: float
) -> dict:
    """Driving distance/duration via OSRM's public router."""
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{o_lng},{o_lat};{d_lng},{d_lat}"
        "?overview=false"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(url)
        res.raise_for_status()
        data = res.json()

    routes = data.get("routes") or []
    if not routes:
        raise ValueError("no route found between the given points")
    r = routes[0]
    return {
        "distance_km": round(r["distance"] / 1000.0, 2),
        "duration_min": max(1, round(r["duration"] / 60.0)),
        "provider": "osrm-demo",
        "retrieved_at": datetime.now(timezone.utc),
    }


def _weather_text(code: int | None) -> str:
    """Human condition from a WMO weather code (0 = clear …)."""
    table = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
        61: "Light rain", 63: "Rain", 65: "Heavy rain",
        71: "Light snow", 73: "Snow", 75: "Heavy snow",
        80: "Rain showers", 81: "Rain showers", 82: "Violent rain showers",
        95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail",
    }
    return table.get(code, "Unknown")


def dumps(payload: dict) -> str:
    return json.dumps(payload, default=str)
