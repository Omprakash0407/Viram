"""Public + authenticated place-review endpoints (design doc §24)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.modules.reviews import service
from app.modules.reviews.schemas import ReviewCreate, ReviewCreateResponse, ReviewList
from app.modules.users.deps import get_current_user

router = APIRouter(prefix="/places", tags=["reviews"])


@router.get("/{place_slug}/reviews", response_model=ReviewList)
async def list_reviews(
    place_slug: str,
    db: AsyncSession = Depends(get_db),
) -> ReviewList:
    """Public: active reviews for a place + live aggregates."""
    rows, rating_avg, count = await service.list_reviews(db, place_slug=place_slug)
    return ReviewList(
        items=[
            {
                "id": r.id,
                "rating": r.rating,
                "title": r.title,
                "body": r.body,
                "status": r.status,
                "visited_on": r.visited_on,
                "created_at": r.created_at,
                "author": {"display_name": name},
            }
            for r, name in rows
        ],
        rating_avg=rating_avg,
        review_count=count,
    )


@router.post("/{place_slug}/reviews", response_model=ReviewCreateResponse, status_code=201)
async def create_review(
    place_slug: str,
    payload: ReviewCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewCreateResponse:
    """Create a review (auth required; one per author per place → 409 on repeat)."""
    review = await service.create_review(db, user=user, place_slug=place_slug, payload=payload)
    await db.commit()
    rows, rating_avg, count = await service.list_reviews(db, place_slug=place_slug)
    mine = next(r for r, _ in rows if r.id == review.id)
    return ReviewCreateResponse(
        review={
            "id": mine.id,
            "rating": mine.rating,
            "title": mine.title,
            "body": mine.body,
            "status": mine.status,
            "visited_on": mine.visited_on,
            "created_at": mine.created_at,
            "author": {"display_name": user.display_name},
        },
        rating_avg=rating_avg,
        review_count=count,
    )


@router.delete("/reviews/{review_id}", status_code=204)
async def delete_review(
    review_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete own review (admin may delete any); aggregates recalc in-transaction."""
    await service.delete_review(db, user=user, review_id=review_id)
    await db.commit()
