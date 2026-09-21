"""Guarded tool execution for Vira AI (beta).

Every tool is the SAME service function the REST endpoints use — ownership,
validation and audit rules apply identically. The AI can never do anything a
signed-in user could not do through the UI. Results are dicts sized for the
model, not full API payloads.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailedError
from app.models.geo import City
from app.models.user import User
from app.modules.chat import retrieval
from app.modules.planning import service as planning_service


async def execute_tool(
    name: str, args: dict, db: AsyncSession, user: User
) -> dict:
    """Dispatch a model-proposed tool call through the guarded services."""
    if name == "suggest_trip":
        return await _suggest_trip(db, user=user, args=args)
    if name == "get_weather":
        return await _get_weather(db, args=args)
    if name == "list_my_trips":
        return await _list_my_trips(db, user=user)
    return {"error": f"Unknown tool {name}"}


def _parse_iso(value: object) -> date:
    d = date.fromisoformat(str(value))
    return d


# The model sometimes emits label-style values ("food, culture", "moderate");
# map them onto the platform's canonical enum keys before validation.
_MOOD_ALIASES = {
    "food": "FOOD_CULTURE", "culture": "FOOD_CULTURE", "food_culture": "FOOD_CULTURE",
    "nature": "NATURE_RELAXATION", "relaxation": "NATURE_RELAXATION",
    "nature_relaxation": "NATURE_RELAXATION", "quiet": "NATURE_RELAXATION",
    "city": "CITY_LIFE", "city_life": "CITY_LIFE", "nightlife": "CITY_LIFE",
    "adventure": "ADVENTURE_THRILL", "thrill": "ADVENTURE_THRILL",
    "adventure_thrill": "ADVENTURE_THRILL", "trekking": "ADVENTURE_THRILL",
}
_BUDGET_ALIASES = {
    "budget": "BUDGET", "moderate": "MODERATE", "mid": "MODERATE",
    "premium": "PREMIUM", "executive": "EXECUTIVE", "luxury": "PREMIUM",
}


async def _suggest_trip(db: AsyncSession, *, user: User, args: dict) -> dict:
    city = await retrieval.resolve_city(db, name=str(args.get("city", "")))
    if city is None:
        return {"error": f"No verified city named '{args.get('city')}'. Suggest Odisha cities."}

    try:
        starts = _parse_iso(args.get("start_date"))
        ends = _parse_iso(args.get("end_date"))
    except (TypeError, ValueError):
        return {"error": "Dates must be ISO YYYY-MM-DD."}
    if ends < starts:
        return {"error": "end_date is before start_date."}
    if starts < date.today():
        return {"error": "start_date is in the past — propose a trip starting today or later."}
    if starts > date.today() + timedelta(days=365):
        return {"error": "start_date is more than a year ahead — propose nearer dates."}
    if (ends - starts).days > 29:
        return {"error": "Trips longer than 30 days are not supported."}

    moods = [str(m).strip().lower().replace(" ", "_") for m in (args.get("moods") or [])]
    moods = [_MOOD_ALIASES.get(m, m.upper()) for m in moods]
    valid_moods = {"NATURE_RELAXATION", "CITY_LIFE", "ADVENTURE_THRILL", "FOOD_CULTURE"}
    moods = [m for m in moods if m in valid_moods]
    if not moods:
        moods = ["FOOD_CULTURE"]  # a sensible default; noted in the reply
    budget = str(args.get("budget_tier", "MODERATE")).strip().lower()
    budget = _BUDGET_ALIASES.get(budget, budget.upper())
    if budget not in {"BUDGET", "MODERATE", "PREMIUM", "EXECUTIVE"}:
        budget = "MODERATE"
    try:
        party = int(args.get("party_size") or 1)
    except (TypeError, ValueError):
        party = 1
    party = max(1, min(50, party))

    trip = await planning_service.create_trip(
        db,
        user=user,
        city_id=city.id,
        starts_on=starts,
        ends_on=ends,
        party_size=party,
        moods=moods,
        budget_tier=budget,
    )
    await db.flush()

    # Persisted run + itinerary (same pipeline as the wizard's final step).
    run, _items = await planning_service.generate_recommendations(
        db, user=user, trip=trip, persist=True
    )
    if run is not None:
        await planning_service.accept_recommendations(
            db, user=user, trip=trip, run_id=run.id, item_ids=[]
        )
    await planning_service.generate_itinerary(db, user=user, trip=trip, run_id=run.id if run else None)

    detail = await planning_service.get_trip_detail(db, user=user, trip_id=trip.id)
    days = (detail.get("itinerary") or {}).get("days") or []
    return {
        "trip_id": str(trip.id),
        "city": city.name,
        "dates": f"{trip.starts_on.isoformat()} to {trip.ends_on.isoformat()}",
        "itinerary_summary": [
            {
                "day": d["day_number"],
                "places": [i["title"] for i in d["items"]][:6],
            }
            for d in days
        ][:10],
    }


async def _get_weather(db: AsyncSession, *, args: dict) -> dict:
    from app.modules.intelligence import service as intelligence_service

    city = await retrieval.resolve_city(db, name=str(args.get("city", "")))
    if city is None:
        return {"error": f"No verified city named '{args.get('city')}'."}
    try:
        snap = await intelligence_service.get_weather_cached(
            db, city_id=city.id, target_date=args.get("date")
        )
    except intelligence_service.WeatherUnavailableError:
        return {"error": "Weather provider is not responding right now — try again later."}
    except ValidationFailedError:
        return {"error": "date must be ISO YYYY-MM-DD."}
    return {
        "city": city.name,
        "date": snap["date"],
        "temperature_c": snap["temperature_c"],
        "condition": snap["condition"],
        "high_c": snap["tmax_c"],
        "low_c": snap["tmin_c"],
        "cached": snap["cached"],
    }


async def _list_my_trips(db: AsyncSession, *, user: User) -> dict:
    trips = await planning_service.list_trips(db, user=user)
    return {
        "trips": [
            {
                "id": str(t.id),
                "city": (await db.get(City, t.city_id)).name,
                "dates": f"{t.starts_on.isoformat()} to {t.ends_on.isoformat()}",
                "status": t.status,
            }
            for t in trips[:8]
        ]
    }
