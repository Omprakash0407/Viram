"""Trip planning endpoints (mock steps 1–6). All owner-scoped, auth required."""

import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.modules.planning import service
from app.modules.planning.schemas import TripCreate
from app.modules.users.deps import get_current_user

router = APIRouter(prefix="/trips", tags=["trips"])


class AcceptRequest(BaseModel):
    run_id: uuid.UUID
    item_ids: list[uuid.UUID] = Field(default_factory=list)


class ItineraryRequest(BaseModel):
    run_id: uuid.UUID | None = None


class CustomItemRequest(BaseModel):
    day_number: int = Field(ge=1)
    custom_title: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=500)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_trip(
    payload: TripCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    trip = await service.create_trip(
        db,
        user=user,
        city_id=payload.city_id,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        party_size=payload.party_size,
        moods=payload.moods,
        budget_tier=payload.budget_tier,
    )
    await db.commit()
    return {
        "id": str(trip.id),
        "status": trip.status,
        "starts_on": trip.starts_on.isoformat(),
        "ends_on": trip.ends_on.isoformat(),
        "party_size": trip.party_size,
        "preferences": trip.preferences_snapshot,
    }


@router.get("")
async def list_trips(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    trips = await service.list_trips(db, user=user)
    return {
        "items": [
            {
                "id": str(t.id),
                "status": t.status,
                "starts_on": t.starts_on.isoformat(),
                "ends_on": t.ends_on.isoformat(),
                "party_size": t.party_size,
            }
            for t in trips
        ]
    }


@router.post("/{trip_id}/recommendations")
async def generate_recommendations(
    trip_id: uuid.UUID,
    persist: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mock step 5: personalized plan. Transient unless persist=true (§13)."""
    trip = await service._trip_or_404(db, trip_id, user)
    run, items = await service.generate_recommendations(
        db, user=user, trip=trip, persist=persist
    )
    if run is not None:
        await db.commit()  # persisted runs must survive the request session
    if run is None:
        # transient: regenerate the result set without writing anything
        result = await service.engine.generate(
            db,
            city_id=trip.city_id,
            moods=(trip.preferences_snapshot or {}).get("moods", []),
            budget_tier=(trip.preferences_snapshot or {}).get("budget_tier", "MODERATE"),
            days=service.trip_day_count(trip),
        )
        return {
            "run_id": None,
            "persisted": False,
            "items": [
                {
                    "place_id": str(i.place_id),
                    "score": float(i.score) if i.score is not None else None,
                    "classification": i.classification,
                    "explanation": i.explanation,
                }
                for i in result.items
            ],
        }
    return {
        "run_id": str(run.id),
        "persisted": True,
        "engine": {"name": run.engine_name, "version": run.engine_version},
        "items": [
            {
                "id": str(i.id),
                "place_id": str(i.place_id),
                "rank": i.rank,
                "score": float(i.score) if i.score is not None else None,
                "classification": i.classification,
                "explanation": i.explanation,
                "accepted": i.accepted,
            }
            for i in items
        ],
    }


@router.post("/{trip_id}/recommendations/accept")
async def accept_recommendations(
    trip_id: uuid.UUID,
    payload: AcceptRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    trip = await service._trip_or_404(db, trip_id, user)
    chosen = await service.accept_recommendations(
        db, user=user, trip=trip, run_id=payload.run_id, item_ids=payload.item_ids
    )
    await db.commit()
    return {"accepted_count": len(chosen)}


@router.post("/{trip_id}/itinerary", status_code=status.HTTP_201_CREATED)
async def generate_itinerary(
    trip_id: uuid.UUID,
    payload: ItineraryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    trip = await service._trip_or_404(db, trip_id, user)
    await service.generate_itinerary(db, user=user, trip=trip, run_id=payload.run_id)
    await db.commit()
    detail = await service.get_trip_detail(db, user=user, trip_id=trip.id)
    return {"itinerary": detail["itinerary"]}


@router.get("/{trip_id}")
async def get_trip(
    trip_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await service.get_trip_detail(db, user=user, trip_id=trip_id)


@router.post("/{trip_id}/itinerary/items", status_code=status.HTTP_201_CREATED)
async def add_custom_item(
    trip_id: uuid.UUID,
    payload: CustomItemRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = await service.add_custom_item(
        db,
        user=user,
        trip_id=trip_id,
        day_number=payload.day_number,
        custom_title=payload.custom_title,
        note=payload.note,
    )
    await db.commit()
    return {"id": str(item.id), "position": item.position, "title": item.custom_title}


@router.delete("/{trip_id}/itinerary/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(
    trip_id: uuid.UUID,
    item_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.remove_item(db, user=user, trip_id=trip_id, item_id=item_id)
    await db.commit()
