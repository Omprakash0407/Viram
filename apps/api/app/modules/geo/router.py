"""Public geography read endpoints (explore index + place detail pages)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.geo import City, Place, State

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/states")
async def list_states(db: AsyncSession = Depends(get_db)) -> dict:
    rows = (await db.scalars(select(State).order_by(State.name))).all()
    return {"items": [{"id": str(s.id), "name": s.name, "slug": s.slug} for s in rows]}


@router.get("/cities")
async def list_cities(
    state_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(City).order_by(City.name)
    if state_id is not None:
        stmt = stmt.where(City.state_id == state_id)
    rows = (await db.scalars(stmt)).all()
    return {
        "items": [
            {
                "id": str(c.id),
                "name": c.name,
                "slug": c.slug,
                "state_id": str(c.state_id),
                "latitude": float(c.latitude),
                "longitude": float(c.longitude),
            }
            for c in rows
        ]
    }


@router.get("/places/{slug}")
async def get_place_detail(slug: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Full public detail for one place (explore detail page).

    404 for unknown slugs and for non-ACTIVE places. `details` is the
    admin-managed editorial payload (experiences, tips, gallery, nearby);
    nearby entries are resolved to live slugs so the page never links to a
    404, unresolved ones are dropped.
    """
    row = (
        await db.execute(
            select(Place, City, State)
            .join(City, Place.city_id == City.id)
            .join(State, City.state_id == State.id)
            .where(Place.slug == slug, Place.status == "ACTIVE")
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Place not found")
    place, city, state = row

    details = dict(place.details) if place.details else None
    if details and isinstance(details.get("nearby"), list):
        slugs = [n.get("slug") for n in details["nearby"] if isinstance(n, dict) and n.get("slug")]
        resolved: dict[str, Place] = {}
        if slugs:
            rows = (
                await db.scalars(
                    select(Place).where(Place.slug.in_(slugs), Place.status == "ACTIVE")
                )
            ).all()
            resolved = {p.slug: p for p in rows}
        details["nearby"] = [
            {
                "slug": n["slug"],
                "name": resolved[n["slug"]].name,
                "label": n.get("label"),
            }
            for n in details["nearby"]
            if isinstance(n, dict) and n.get("slug") in resolved
        ]

    return {
        "id": str(place.id),
        "name": place.name,
        "slug": place.slug,
        "description": place.description,
        "classification": place.classification,
        "lesser_known_note": place.lesser_known_note,
        "rating_avg": float(place.rating_avg) if place.rating_avg else None,
        "review_count": place.review_count,
        "typical_visit_minutes": place.typical_visit_minutes,
        "opening_hours": place.opening_hours,
        "latitude": float(place.latitude),
        "longitude": float(place.longitude),
        "city": {"name": city.name, "slug": city.slug},
        "state": {"name": state.name, "slug": state.slug},
        "details": details,
    }


@router.get("/places")
async def list_places(
    city_id: uuid.UUID | None = None,
    classification: str | None = Query(default=None, pattern="^(POPULAR|LESSER_KNOWN)$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(Place).where(Place.status == "ACTIVE").order_by(Place.name)
    if city_id is not None:
        stmt = stmt.where(Place.city_id == city_id)
    if classification is not None:
        stmt = stmt.where(Place.classification == classification)
    rows = (await db.scalars(stmt)).all()
    return {
        "items": [
            {
                "id": str(p.id),
                "name": p.name,
                "slug": p.slug,
                "description": p.description,
                "city_id": str(p.city_id),
                "classification": p.classification,
                "lesser_known_note": p.lesser_known_note,
                "rating_avg": float(p.rating_avg) if p.rating_avg else None,
                "popularity_score": float(p.popularity_score) if p.popularity_score else None,
                "typical_visit_minutes": p.typical_visit_minutes,
            }
            for p in rows
        ]
    }
