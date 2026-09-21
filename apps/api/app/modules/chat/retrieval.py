"""Retrieval for Vira AI (beta): verified platform data + the user's own history.

Rule 8 (nothing invented) is enforced by construction: the AI only sees rows
that are already approved/visible in the database, and every answer must cite
them. Data minimization: the user's own context is summarized, never dumps
(no emails, no payment data, no contact info).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import City, Place, PlaceCategory, State
from app.models.planning import Itinerary, ItineraryDay, ItineraryItem, Trip, TripCompanion
from app.models.user import UserPreference


async def destination_brief(db: AsyncSession, *, city_id: uuid.UUID) -> dict | None:
    """The verified facts about one city: top places + cultural notes."""
    city = await db.get(City, city_id)
    if city is None:
        return None
    state = await db.get(State, city.state_id)
    places = (
        await db.scalars(
            select(Place)
            .where(Place.city_id == city.id, Place.status == "ACTIVE")
            .order_by(Place.popularity_score.desc().nullslast())
            .limit(14)
        )
    ).all()
    cats = {
        c.id: c.slug
        for c in (
            await db.scalars(select(PlaceCategory)).all()
        )
    }
    out = []
    for p in places:
        entry = {
            "name": p.name,
            "category": cats.get(p.category_id, "unknown"),
            "classification": p.classification,
            "rating": float(p.rating_avg) if p.rating_avg is not None else None,
            "visit_minutes": p.typical_visit_minutes,
            "description": (p.description or "")[:220],
        }
        details = p.details or {}
        # Curated editorial content is the most trustworthy text we have.
        for key in ("highlights", "best_time", "entry_fee", "location"):
            if details.get(key):
                entry[key] = details[key] if not isinstance(details[key], list) else details[key][:4]
        out.append(entry)
    return {
        "city": city.name,
        "state": state.name if state else None,
        "places": out,
    }


async def user_context(db: AsyncSession, *, user_id: uuid.UUID) -> dict:
    """The traveller's own data: preferences + trip history (concise)."""
    prefs = await db.get(UserPreference, user_id)
    trips = (
        await db.scalars(
            select(Trip)
            .where(Trip.user_id == user_id)
            .order_by(Trip.created_at.desc())
            .limit(6)
        )
    ).all()
    city_names: dict[uuid.UUID, str] = {}
    trip_rows = []
    for t in trips:
        if t.city_id not in city_names:
            c = await db.get(City, t.city_id)
            city_names[t.city_id] = c.name if c else "unknown city"
        itinerary = await db.scalar(select(Itinerary).where(Itinerary.trip_id == t.id))
        titles: list[str] = []
        if itinerary is not None:
            day_ids = (
                await db.scalars(
                    select(ItineraryDay.id).where(ItineraryDay.itinerary_id == itinerary.id)
                )
            ).all()
            if day_ids:
                items = (
                    await db.scalars(
                        select(ItineraryItem).where(ItineraryItem.itinerary_day_id.in_(day_ids))
                    )
                ).all()
                from app.models.geo import Place

                for it in items[:20]:
                    if it.place_id:
                        p = await db.get(Place, it.place_id)
                        if p:
                            titles.append(p.name)
                    elif it.custom_title:
                        titles.append(it.custom_title)
        trip_rows.append(
            {
                "city": city_names[t.city_id],
                "dates": f"{t.starts_on.isoformat()} to {t.ends_on.isoformat()}",
                "status": t.status,
                "party_size": t.party_size,
                "moods": (t.preferences_snapshot or {}).get("moods", []),
                "budget": (t.preferences_snapshot or {}).get("budget_tier"),
                "visited_places": titles[:10],
            }
        )
    return {
        "interests": prefs.interests if prefs else [],
        "pace": prefs.pace if prefs else None,
        "budget_level": prefs.budget_level if prefs else None,
        "recent_trips": trip_rows,
    }


async def resolve_city(db: AsyncSession, *, name: str) -> City | None:
    """Resolve a free-text city/state mention to the canonical City row."""
    q = name.strip().lower()
    if not q:
        return None
    city = (
        await db.scalars(
            select(City).where(City.slug == q.replace(" ", "-").lower())
        )
    ).first()
    if city:
        return city
    like = f"%{q}%"
    city = (await db.scalars(select(City).where(City.name.ilike(like)).limit(1))).first()
    if city:
        return city
    state = (await db.scalars(select(State).where(State.name.ilike(like)).limit(1))).first()
    if state:
        city = (
            await db.scalars(select(City).where(City.state_id == state.id).limit(1))
        ).first()
    return city


async def shared_trip_ids(db: AsyncSession, *, user_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (
        await db.scalars(
            select(TripCompanion.trip_id).where(
                TripCompanion.companion_user_id == user_id,
                TripCompanion.status == "ACTIVE",
            )
        )
    ).all()
    return list(rows)
