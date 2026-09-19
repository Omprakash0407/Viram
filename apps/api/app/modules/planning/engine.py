"""Replaceable recommendation engine.

Contract (design doc §13): any engine returns an EngineResult with
(engine_name, engine_version, preference_snapshot, items). A future
AIRecommendationEngine implements the same interface with zero schema changes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import Place, PlaceCategory
from app.modules.planning.schemas import MOOD_CATEGORIES


@dataclass(frozen=True)
class EngineItem:
    place_id: uuid.UUID
    score: Decimal | None
    classification: str
    explanation: str


@dataclass(frozen=True)
class EngineResult:
    engine_name: str
    engine_version: str
    preference_snapshot: dict
    items: list[EngineItem]


class RuleBasedRecommendationEngine:
    """Deterministic v1 scoring: mood→category match + rating + popularity,
    with a guaranteed lesser-known share in the output.

    Reads nothing from user tables; writes nothing — the service layer decides
    what to persist (transient vs persistent, design doc §13).
    """

    ENGINE_NAME = "RuleBasedRecommendationEngine"
    ENGINE_VERSION = "rules-v1"

    # every plan keeps a hidden-gem share (design doc §12, mock step 5)
    LESSER_KNOWN_TARGET_SHARE = 0.25

    async def generate(
        self,
        db: AsyncSession,
        *,
        city_id: uuid.UUID,
        moods: list[str],
        budget_tier: str,
        days: int,
    ) -> EngineResult:
        category_slugs = [s for mood in moods for s in MOOD_CATEGORIES[mood]]
        stmt = (
            select(Place)
            .join(PlaceCategory, Place.category_id == PlaceCategory.id)
            .where(
                Place.city_id == city_id,
                Place.status == "ACTIVE",
                PlaceCategory.slug.in_(category_slugs),
            )
            .limit(200)
        )
        places = (await db.scalars(stmt)).all()
        mood_matched = True
        if not places and moods:
            # Graceful degradation: the selected moods have no category matches
            # in this city (e.g. CITY_LIFE in a temple town with no 'fun' or
            # 'markets' places). An empty plan dead-ends the wizard, so fall
            # back to the city's best places and label the run honestly.
            mood_matched = False
            fallback = (
                select(Place)
                .where(Place.city_id == city_id, Place.status == "ACTIVE")
                .limit(200)
            )
            places = (await db.scalars(fallback)).all()
        if not places:
            return EngineResult(self.ENGINE_NAME, self.ENGINE_VERSION, {"city_id": str(city_id), "moods": moods, "budget_tier": budget_tier, "days": days, "mood_matched": False}, [])

        scored = [(p, self._score(p, category_slugs, mood_matched)) for p in places]
        scored.sort(key=lambda pair: (-pair[1], pair[0].name))
        items = self._to_items(scored, category_slugs, mood_matched)
        snapshot = {
            "city_id": str(city_id),
            "moods": moods,
            "budget_tier": budget_tier,
            "days": days,
            "category_slugs": category_slugs,
            "mood_matched": mood_matched,
        }
        return EngineResult(self.ENGINE_NAME, self.ENGINE_VERSION, snapshot, items)

    def _score(self, place: Place, category_slugs: list[str], mood_matched: bool = True) -> Decimal:
        rating = float(place.rating_avg) if place.rating_avg is not None else 3.0
        popularity = (float(place.popularity_score) / 100.0) if place.popularity_score is not None else 0.5
        # Full match when the mood filter produced candidates; fallback picks
        # score lower on the interest term (0.6) so true mood matches, when any
        # exist, always outrank them.
        category_match = 1.0 if mood_matched else 0.6
        lesser_bonus = 0.15 if place.classification == "LESSER_KNOWN" else 0.0
        raw = 3.0 * category_match + 2.0 * rating + 1.5 * popularity + lesser_bonus
        return Decimal(str(raw)).quantize(Decimal("0.01"))

    def _to_items(
        self, scored: list[tuple[Place, Decimal]], category_slugs: list[str], mood_matched: bool = True
    ) -> list[EngineItem]:
        """Rank scored places, enforce the lesser-known share, and write a
        human-readable explanation for each item (design doc §13)."""
        target_lesser = int(len(scored) * self.LESSER_KNOWN_TARGET_SHARE)
        popular_pool = [pair for pair in scored if pair[0].classification == "POPULAR"]
        lesser_pool = [pair for pair in scored if pair[0].classification == "LESSER_KNOWN"]

        ordered: list[tuple[Place, Decimal]] = []
        while popular_pool or lesser_pool:
            # 3 popular picks, then one hidden gem while the share is unmet;
            # every branch consumes from a pool, so the loop always terminates.
            for _ in range(3):
                if not popular_pool:
                    break
                ordered.append(popular_pool.pop(0))
            taken_lesser = sum(1 for p, _ in ordered if p.classification == "LESSER_KNOWN")
            if lesser_pool and (taken_lesser < max(target_lesser, 1) or not popular_pool):
                ordered.append(lesser_pool.pop(0))

        items: list[EngineItem] = []
        for rank, (place, score) in enumerate(ordered, start=1):
            if place.classification == "LESSER_KNOWN":
                note = place.lesser_known_note or "a local hidden gem"
                explanation = f"Hidden gem: {note}"
            else:
                bits = [
                    "Closest matches for your interests"
                    if not mood_matched
                    else "Matches your interests"
                ]
                if place.rating_avg is not None:
                    bits.append(f"{place.rating_avg} rating")
                if place.popularity_score is not None:
                    bits.append(f"popularity {int(place.popularity_score)}/100")
                explanation = "; ".join(bits)
            items.append(
                EngineItem(
                    place_id=place.id,
                    score=score,
                    classification=place.classification,
                    explanation=explanation,
                )
            )
        return items
