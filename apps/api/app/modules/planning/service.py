"""Trip & itinerary services.

Flow (mock steps 1–6, design doc §14):
create trip → generate recommendations → accept items → generate itinerary
(one per trip, date-derived days) → customize (add/remove/reorder).
"""

from __future__ import annotations

import math
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.planning.engine import RuleBasedRecommendationEngine

from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.exceptions import ConflictError, ValidationError
from app.models.geo import City, Place
from app.models.planning import (
    Itinerary,
    ItineraryDay,
    ItineraryItem,
    RecommendationItem,
    RecommendationRun,
    Trip,
)
from app.models.user import User

engine = RuleBasedRecommendationEngine()

DAY_START_POSITION_STEP = 10  # gap between items so inserts rarely renumber


async def _city_or_404(db: AsyncSession, city_id: uuid.UUID) -> City:
    city = await db.get(City, city_id)
    if city is None:
        raise NotFoundError("City not found.")
    return city


async def _trip_or_404(db: AsyncSession, trip_id: uuid.UUID, user: User) -> Trip:
    trip = await db.get(Trip, trip_id)
    if trip is None:
        raise NotFoundError("Trip not found.")
    if trip.user_id != user.id:
        raise PermissionDeniedError("This trip belongs to another traveller.")
    return trip


async def _trip_for_read(
    db: AsyncSession, trip_id: uuid.UUID, user: User
) -> tuple[Trip, str]:
    """Read access = trip head OR accepted companion (travelling together).

    Mutations keep using _trip_or_404 — companions are read-only viewers.
    """
    from app.modules.planning import companions_service

    trip = await db.get(Trip, trip_id)
    if trip is None:
        raise NotFoundError("Trip not found.")
    if trip.user_id == user.id:
        return trip, "HEAD"
    if await companions_service.is_active_companion(
        db, trip_id=trip_id, user_id=user.id
    ):
        return trip, "COMPANION"
    raise PermissionDeniedError("This trip belongs to another traveller.")


async def create_trip(
    db: AsyncSession,
    *,
    user: User,
    city_id: uuid.UUID,
    starts_on: date,
    ends_on: date,
    party_size: int,
    moods: list[str],
    budget_tier: str,
) -> Trip:
    """Create the trip and persist the preference snapshot (design doc §14)."""
    await _city_or_404(db, city_id)
    days = (ends_on - starts_on).days + 1
    snapshot = {
        "moods": moods,
        "budget_tier": budget_tier,
        "party_size": party_size,
        "days": days,
    }
    trip = Trip(
        user_id=user.id,
        city_id=city_id,
        starts_on=starts_on,
        ends_on=ends_on,
        party_size=party_size,
        status="PLANNING",
        preferences_snapshot=snapshot,
    )
    db.add(trip)
    await db.flush()
    return trip


def trip_day_count(trip: Trip) -> int:
    return (trip.ends_on - trip.starts_on).days + 1


async def generate_recommendations(
    db: AsyncSession, *, user: User, trip: Trip, persist: bool
) -> tuple[RecommendationRun | None, list[RecommendationItem]]:
    """Run the engine. Persisted only when the flow saves it (design doc §13:
    casual browsing stays transient; saved/accepted runs are kept)."""
    snapshot = dict(trip.preferences_snapshot or {})
    moods = snapshot.get("moods") or []
    budget_tier = snapshot.get("budget_tier") or "MODERATE"
    days = trip_day_count(trip)

    result = await engine.generate(
        db, city_id=trip.city_id, moods=moods, budget_tier=budget_tier, days=days
    )
    if not persist:
        return None, []

    run = RecommendationRun(
        user_id=user.id,
        trip_id=trip.id,
        engine_name=result.engine_name,
        engine_version=result.engine_version,
        preference_snapshot=result.preference_snapshot,
    )
    db.add(run)
    await db.flush()
    for rank, item in enumerate(result.items, start=1):
        db.add(
            RecommendationItem(
                run_id=run.id,
                place_id=item.place_id,
                rank=rank,
                score=item.score,
                classification=item.classification,
                explanation=item.explanation,
                accepted=False,
            )
        )
    await db.flush()
    # re-select so callers get plain loaded rows (no lazy-load outside async ctx)
    saved = list(
        (
            await db.scalars(
                select(RecommendationItem)
                .where(RecommendationItem.run_id == run.id)
                .order_by(RecommendationItem.rank)
            )
        ).all()
    )
    return run, saved


async def _run_or_404(db: AsyncSession, run_id: uuid.UUID, user: User) -> RecommendationRun:
    run = await db.get(RecommendationRun, run_id)
    if run is None:
        raise NotFoundError("Recommendation run not found.")
    if run.user_id != user.id:
        raise PermissionDeniedError("This recommendation run belongs to another traveller.")
    return run


async def accept_recommendations(
    db: AsyncSession, *, user: User, trip: Trip, run_id: uuid.UUID, item_ids: list[uuid.UUID]
) -> list[RecommendationItem]:
    """Mark chosen items accepted; all items in the run if none specified."""
    run = await _run_or_404(db, run_id, user)
    if run.trip_id != trip.id:
        raise ValidationError("This recommendation run is not linked to this trip.")

    stmt = select(RecommendationItem).where(RecommendationItem.run_id == run.id)
    all_items = list((await db.scalars(stmt)).all())
    wanted = set(item_ids) if item_ids else {i.id for i in all_items}
    chosen = [i for i in all_items if i.id in wanted]
    if not chosen:
        raise ValidationError("No matching recommendation items to accept.")
    for item in chosen:
        item.accepted = True
    await db.flush()
    return chosen


async def generate_itinerary(
    db: AsyncSession, *, user: User, trip: Trip, run_id: uuid.UUID | None
) -> Itinerary:
    """Build the one active itinerary: one day row per trip date, accepted
    recommendation items distributed round-robin, provenance preserved
    (itinerary_items.recommendation_item_id, design doc §14)."""
    existing = await db.scalar(select(Itinerary).where(Itinerary.trip_id == trip.id))
    if existing is not None:
        raise ConflictError("This trip already has an itinerary; customize it instead.")

    accepted: list[RecommendationItem]
    if run_id is not None:
        run = await _run_or_404(db, run_id, user)
        if run.trip_id != trip.id:
            raise ValidationError("This recommendation run is not linked to this trip.")
        stmt = (
            select(RecommendationItem)
            .where(RecommendationItem.run_id == run.id, RecommendationItem.accepted.is_(True))
            .order_by(RecommendationItem.rank)
        )
        accepted = list((await db.scalars(stmt)).all())
    else:
        # no run: place-only itinerary from the trip snapshot (degenerate flow)
        accepted = []

    days_n = trip_day_count(trip)
    if accepted and days_n > 0:
        per_day = math.ceil(len(accepted) / days_n)
    else:
        per_day = 0

    itinerary = Itinerary(trip_id=trip.id, status="ACTIVE")
    db.add(itinerary)
    await db.flush()

    for day_number in range(1, days_n + 1):
        db.add(
            ItineraryDay(
                itinerary_id=itinerary.id,
                day_number=day_number,
                date=trip.starts_on + timedelta(days=day_number - 1),
            )
        )
    await db.flush()

    day_rows = list(
        (
            await db.scalars(
                select(ItineraryDay)
                .where(ItineraryDay.itinerary_id == itinerary.id)
                .order_by(ItineraryDay.day_number)
            )
        ).all()
    )
    for index, rec in enumerate(accepted):
        day = day_rows[min(index // per_day, days_n - 1)] if per_day else day_rows[0]
        db.add(
            ItineraryItem(
                itinerary_day_id=day.id,
                position=(index % per_day) * DAY_START_POSITION_STEP if per_day else 0,
                place_id=rec.place_id,
                recommendation_item_id=rec.id,
            )
        )
    await db.flush()
    return itinerary


async def get_trip_detail(db: AsyncSession, *, user: User, trip_id: uuid.UUID) -> dict:
    """Trip + itinerary, readable by the head or an accepted companion
    (travelling together). Bookings/payments are served by commerce and stay
    owner-only regardless."""
    trip, viewer_role = await _trip_for_read(db, trip_id, user)
    city = await db.get(City, trip.city_id)

    itinerary = await db.scalar(select(Itinerary).where(Itinerary.trip_id == trip.id))
    days_out: list[dict] = []
    if itinerary is not None:
        day_rows = (
            await db.scalars(
                select(ItineraryDay)
                .where(ItineraryDay.itinerary_id == itinerary.id)
                .order_by(ItineraryDay.day_number)
            )
        ).all()
        day_ids = [d.id for d in day_rows]
        item_rows: list[ItineraryItem] = []
        if day_ids:
            item_rows = list(
                (
                    await db.scalars(
                        select(ItineraryItem)
                        .where(ItineraryItem.itinerary_day_id.in_(day_ids))
                        .order_by(ItineraryItem.itinerary_day_id, ItineraryItem.position)
                    )
                ).all()
            )
        place_ids = {i.place_id for i in item_rows if i.place_id is not None}
        places: dict[uuid.UUID, Place] = {}
        if place_ids:
            place_rows = (await db.scalars(select(Place).where(Place.id.in_(place_ids)))).all()
            places = {p.id: p for p in place_rows}
        items_by_day: dict[uuid.UUID, list[ItineraryItem]] = {}
        for i in item_rows:
            items_by_day.setdefault(i.itinerary_day_id, []).append(i)
        for d in day_rows:
            items_out = []
            for i in items_by_day.get(d.id, []):
                place = places.get(i.place_id) if i.place_id else None
                items_out.append(
                    {
                        "id": str(i.id),
                        "position": i.position,
                        "title": place.name if place else (i.custom_title or "Visit"),
                        "place_id": str(i.place_id) if i.place_id else None,
                        "start_time": i.start_time.isoformat() if i.start_time else None,
                        "duration_minutes": i.duration_minutes,
                        "note": i.note,
                    }
                )
            days_out.append(
                {"day_number": d.day_number, "date": d.date.isoformat(), "items": items_out}
            )

    return {
        "id": str(trip.id),
        "status": trip.status,
        "viewer_role": viewer_role,
        "city": {"id": str(city.id), "name": city.name} if city else None,
        "starts_on": trip.starts_on.isoformat(),
        "ends_on": trip.ends_on.isoformat(),
        "party_size": trip.party_size,
        "preferences": trip.preferences_snapshot,
        "itinerary": {"id": str(itinerary.id), "status": itinerary.status, "days": days_out}
        if itinerary
        else None,
    }


async def add_custom_item(
    db: AsyncSession, *, user: User, trip_id: uuid.UUID, day_number: int,
    custom_title: str, note: str | None = None,
) -> ItineraryItem:
    """Customize: add a non-place item (café, rest, travel buffer) to a day."""
    trip = await _trip_or_404(db, trip_id, user)
    itinerary = await db.scalar(select(Itinerary).where(Itinerary.trip_id == trip.id))
    if itinerary is None:
        raise ValidationError("Generate the itinerary before customizing it.")
    day = await db.scalar(
        select(ItineraryDay).where(
            ItineraryDay.itinerary_id == itinerary.id,
            ItineraryDay.day_number == day_number,
        )
    )
    if day is None:
        raise NotFoundError(f"Day {day_number} does not exist for this trip.")
    max_pos = await db.scalar(
        select(func.max(ItineraryItem.position)).where(ItineraryItem.itinerary_day_id == day.id)
    )
    next_pos = DAY_START_POSITION_STEP if max_pos is None else max_pos + DAY_START_POSITION_STEP
    item = ItineraryItem(
        itinerary_day_id=day.id,
        position=next_pos,
        place_id=None,
        custom_title=custom_title.strip(),
        note=note,
    )
    db.add(item)
    await db.flush()
    return item


async def extend_trip(
    db: AsyncSession, *, user: User, trip_id: uuid.UUID, days: int
) -> Trip:
    """Extend the trip by N days (chat-driven edits). Keeps the active
    itinerary in sync by appending the new day rows; existing items and any
    bookings are untouched (design rule 13)."""
    trip = await _trip_or_404(db, trip_id, user)
    if days < 1 or days > 30:
        raise ValidationError("Days to add must be between 1 and 30.")
    itinerary = await db.scalar(select(Itinerary).where(Itinerary.trip_id == trip.id))
    max_day: int | None = None
    if itinerary is not None:
        max_day = await db.scalar(
            select(func.max(ItineraryDay.day_number)).where(
                ItineraryDay.itinerary_id == itinerary.id
            )
        )
    old_end = trip.ends_on
    trip.ends_on = old_end + timedelta(days=days)
    snapshot = dict(trip.preferences_snapshot or {})
    snapshot["days"] = (trip.ends_on - trip.starts_on).days + 1
    trip.preferences_snapshot = snapshot
    if itinerary is not None and max_day is not None:
        for i in range(1, days + 1):
            db.add(
                ItineraryDay(
                    itinerary_id=itinerary.id,
                    day_number=max_day + i,
                    date=old_end + timedelta(days=i),
                )
            )
    await db.flush()
    return trip


async def remove_item(
    db: AsyncSession, *, user: User, trip_id: uuid.UUID, item_id: uuid.UUID
) -> None:
    """Customize: remove one itinerary item. Ownership checked on the trip and
    that the item really belongs to that trip (prevents cross-trip IDOR)."""
    trip = await _trip_or_404(db, trip_id, user)
    row = await db.get(ItineraryItem, item_id)
    if row is None:
        raise NotFoundError("Itinerary item not found.")
    day = await db.get(ItineraryDay, row.itinerary_day_id)
    itinerary = await db.get(Itinerary, day.itinerary_id)
    if itinerary.trip_id != trip.id:
        raise NotFoundError("Itinerary item not found for this trip.")
    await db.delete(row)
    await db.flush()


async def list_trips(db: AsyncSession, *, user: User) -> list[Trip]:
    stmt = (
        select(Trip)
        .where(Trip.user_id == user.id)
        .order_by(Trip.created_at.desc())
    )
    return list((await db.scalars(stmt)).all())
