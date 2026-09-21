"""Interaction models: place reviews (design doc §24 — typed review entities).

Hotel/Guide/Business reviews arrive with the provider-review slice; PlaceReview
is the traveller-facing one for destination pages.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import created_at
from app.models.base import updated_at  # noqa: F401 (consistency with other models)
from app.core.database import Base


class PlaceReview(Base):
    """A traveller's review of a place (design doc §24).

    - one review per author per place (duplicate prevention),
    - rating 1..5 enforced in the DB, not just the schema,
    - status supports later moderation without deleting history,
    - booking-gated submission is enforced at the service layer (needs trip/
      booking context the model cannot know about).
    """

    __tablename__ = "place_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(140))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # PENDING reviews are not publicly listed until moderated (MVP: auto-ACTIVE)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    visited_on: Mapped[str | None] = mapped_column(String(20))  # free month/year label

    created_at: Mapped[object] = created_at()

    __table_args__ = (
        UniqueConstraint("place_id", "author_id", name="uq_place_reviews_place_author"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_place_reviews_rating_1_5"),
        CheckConstraint(
            "status IN ('PENDING','ACTIVE','HIDDEN')", name="ck_place_reviews_status"
        ),
    )
