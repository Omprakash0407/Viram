"""Request/response schemas for the commerce module (design doc §15–§18)."""

import uuid
from datetime import date

from pydantic import BaseModel, Field, model_validator


class HotelBookingCreate(BaseModel):
    hotel_id: uuid.UUID
    room_type_id: uuid.UUID
    check_in_date: date
    check_out_date: date
    rooms_count: int = Field(default=1, ge=1, le=10)
    trip_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _dates_ordered(self) -> "HotelBookingCreate":
        if self.check_out_date <= self.check_in_date:
            raise ValueError("check_out_date must be after check_in_date")
        return self


class GuideBookingCreate(BaseModel):
    guide_profile_id: uuid.UUID
    service_start_date: date
    service_end_date: date
    trip_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _dates_ordered(self) -> "GuideBookingCreate":
        if self.service_end_date < self.service_start_date:
            raise ValueError("service_end_date must be on or after service_start_date")
        return self


class PaymentCreate(BaseModel):
    """One checkout pays at most one hotel + one guide booking (design D5)."""

    hotel_booking_id: uuid.UUID | None = None
    guide_booking_id: uuid.UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _at_least_one(self) -> "PaymentCreate":
        if self.hotel_booking_id is None and self.guide_booking_id is None:
            raise ValueError("At least one of hotel_booking_id / guide_booking_id is required.")
        return self
