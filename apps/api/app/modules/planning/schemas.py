"""Request/response schemas for the planning flow (mock steps 1–6)."""

import uuid
from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

# Canonical mood → place_category slugs. Data-driven, not hardcoded in the engine.
MOOD_CATEGORIES: dict[str, list[str]] = {
    "NATURE_RELAXATION": ["nature", "scenic", "lakes", "wildlife", "parks"],
    "CITY_LIFE": ["city-life", "markets", "museums", "fun"],
    "ADVENTURE_THRILL": ["adventure", "trekking", "wildlife"],
    "FOOD_CULTURE": ["heritage", "food", "culture", "crafts"],
}

MOODS = list(MOOD_CATEGORIES.keys())

BUDGET_TIERS = ["BUDGET", "MODERATE", "PREMIUM", "EXECUTIVE"]


class TripCreate(BaseModel):
    # Mock steps 1–4 captured at trip creation as the reproducible snapshot (design §14)
    city_id: uuid.UUID
    starts_on: date
    ends_on: date
    party_size: int = Field(default=1, ge=1, le=50)
    moods: list[str] = Field(min_length=1)
    budget_tier: str

    @field_validator("moods")
    @classmethod
    def _valid_moods(cls, v: list[str]) -> list[str]:
        cleaned = [m.strip().upper() for m in v]
        invalid = set(cleaned) - set(MOODS)
        if invalid:
            raise ValueError(f"unknown moods: {sorted(invalid)}; valid: {MOODS}")
        return cleaned

    @field_validator("budget_tier")
    @classmethod
    def _valid_budget(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in BUDGET_TIERS:
            raise ValueError(f"budget_tier must be one of {BUDGET_TIERS}")
        return v

    @model_validator(mode="after")
    def _dates_ordered(self) -> "TripCreate":
        if self.ends_on < self.starts_on:
            text = "ends_on must be on or after starts_on"
            raise ValueError(text)
        return self
