"""Place review services (design doc §24).

Rules:
- one review per author per place (DB unique constraint; surfaced as 409),
- only ACTIVE reviews are public and counted in aggregates,
- deleting/creating recomputes places.rating_avg / places.review_count in the
  same transaction so the engine and explore grids stay consistent,
- moderation status exists in the model; the MVP auto-activates new reviews
  (admin moderation arrives with the admin slice).
- Note: design doc §24 gates *bookable-service* reviews behind a completed
  booking; places are not bookable, so place reviews are open to any
  authenticated traveller. Hotel/guide review gates arrive with that slice.
"""

import uuid

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db  # noqa: F401 (consistent imports)
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.exceptions import ConflictError
from app.models.geo import Place
from app.models.reviews import PlaceReview
from app.models.user import User
from app.modules.reviews.schemas import ReviewCreate


async def _place_or_404(db: AsyncSession, place_slug: str) -> Place:
    place = (
        await db.scalar(select(Place).where(Place.slug == place_slug, Place.status == "ACTIVE"))
    )
    if place is None:
        raise NotFoundError("Place not found.")
    return place


async def _recalc_aggregates(db: AsyncSession, place_id: uuid.UUID) -> tuple[float | None, int]:
    row = (
        await db.execute(
            select(func.avg(PlaceReview.rating), func.count(PlaceReview.id)).where(
                PlaceReview.place_id == place_id, PlaceReview.status == "ACTIVE"
            )
        )
    ).one()
    avg, count = row
    rating_avg = round(float(avg), 2) if avg is not None else None
    place = await db.get(Place, place_id)
    if place is not None:
        place.rating_avg = rating_avg
        place.review_count = count
    await db.flush()
    return rating_avg, count


async def list_reviews(db: AsyncSession, *, place_slug: str) -> tuple[list, float | None, int]:
    place = await _place_or_404(db, place_slug)
    rows = (
        await db.execute(
            select(PlaceReview, User.display_name)
            .join(User, PlaceReview.author_id == User.id)
            .where(PlaceReview.place_id == place.id, PlaceReview.status == "ACTIVE")
            .order_by(PlaceReview.created_at.desc())
            .limit(200)
        )
    ).all()
    avg = (
        await db.execute(
            select(func.avg(PlaceReview.rating)).where(
                PlaceReview.place_id == place.id, PlaceReview.status == "ACTIVE"
            )
        )
    ).scalar_one()
    rating_avg = round(float(avg), 2) if avg is not None else None
    return [(r, name) for r, name in rows], rating_avg, len(rows)


async def create_review(
    db: AsyncSession, *, user: User, place_slug: str, payload: ReviewCreate
) -> PlaceReview:
    place = await _place_or_404(db, place_slug)
    review = PlaceReview(
        place_id=place.id,
        author_id=user.id,
        rating=payload.rating,
        title=payload.title,
        body=payload.body,
        visited_on=payload.visited_on,
        status="ACTIVE",
    )
    db.add(review)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError("You have already reviewed this place.") from exc
    await _recalc_aggregates(db, place.id)
    return review


async def delete_review(db: AsyncSession, *, user: User, review_id: uuid.UUID) -> None:
    review = await db.get(PlaceReview, review_id)
    if review is None:
        raise NotFoundError("Review not found.")
    if review.author_id != user.id and user.account_role != "ADMIN":
        raise PermissionDeniedError("You can delete only your own reviews.")
    place_id = review.place_id
    await db.execute(sa_delete(PlaceReview).where(PlaceReview.id == review.id))
    await _recalc_aggregates(db, place_id)
