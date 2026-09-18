"""Commerce services: hotel/guide bookings, payments, webhook processing,
conditional contact access. Design doc §15–§18, §24.

Transactional rule (§18): a SUCCEEDED payment flips its bookings
PENDING_PAYMENT → CONFIRMED in the same transaction; failures leave typed
bookings cancelled rather than deleted (§25). Server-side pricing only —
client-supplied totals are never trusted.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.exceptions import ConflictError, ValidationError
from app.models.commerce import (
    GuideAvailability,
    GuideBooking,
    GuideProfile,
    Hotel,
    HotelBooking,
    Payment,
    PaymentWebhookEvent,
    RoomType,
)
from app.models.user import User
from app.modules.commerce import gateway as gw
from app.modules.commerce.gateway import get_payment_gateway

MAX_BOOKING_HORIZON_DAYS = 365  # sanity bound on future-dated bookings


# --------------------------------------------------------------------------- #
# lookups & ownership
# --------------------------------------------------------------------------- #


async def _hotel_or_404(db: AsyncSession, hotel_id: uuid.UUID) -> Hotel:
    hotel = await db.get(Hotel, hotel_id)
    if hotel is None or hotel.status != "ACTIVE":
        raise NotFoundError("Hotel not found.")
    return hotel


async def _room_type_or_404(db: AsyncSession, hotel_id: uuid.UUID, room_type_id: uuid.UUID) -> RoomType:
    room = await db.get(RoomType, room_type_id)
    if room is None or room.hotel_id != hotel_id:
        raise NotFoundError("Room type not found for this hotel.")
    return room


async def _guide_or_404(db: AsyncSession, guide_profile_id: uuid.UUID) -> GuideProfile:
    guide = await db.get(GuideProfile, guide_profile_id)
    if guide is None:
        raise NotFoundError("Guide profile not found.")
    return guide


async def _trip_owned_or_none(
    db: AsyncSession, trip_id: uuid.UUID | None, user: User
) -> None:
    """ trip_id, when supplied, must belong to the caller (IDOR guard)."""
    if trip_id is None:
        return
    from app.models.planning import Trip

    trip = await db.get(Trip, trip_id)
    if trip is None or trip.user_id != user.id:
        raise ValidationError("trip_id does not reference one of your trips.")


def _validate_horizon(d: date, field: str) -> None:
    today = date.today()
    if d < today:
        raise ValidationError(f"{field} is in the past.")
    if d > today + timedelta(days=MAX_BOOKING_HORIZON_DAYS):
        raise ValidationError(f"{field} is too far in the future (max {MAX_BOOKING_HORIZON_DAYS} days).")


# --------------------------------------------------------------------------- #
# hotel bookings
# --------------------------------------------------------------------------- #


async def create_hotel_booking(
    db: AsyncSession,
    *,
    user: User,
    hotel_id: uuid.UUID,
    room_type_id: uuid.UUID,
    check_in_date: date,
    check_out_date: date,
    rooms_count: int,
    trip_id: uuid.UUID | None,
) -> HotelBooking:
    """Request-based booking with server-side pricing (design §15, D6).

    The MVP does NOT pretend live availability exists: no inventory check is
    performed, and the response copy must never claim guaranteed rooms.
    """
    await _trip_owned_or_none(db, trip_id, user)
    hotel = await _hotel_or_404(db, hotel_id)
    room = await _room_type_or_404(db, hotel.id, room_type_id)
    _validate_horizon(check_in_date, "check_in_date")
    _validate_horizon(check_out_date, "check_out_date")

    nights = (check_out_date - check_in_date).days
    price_paise = room.nightly_rate_paise * nights * rooms_count

    booking = HotelBooking(
        reference_id=gw.new_reference("HB"),
        user_id=user.id,
        trip_id=trip_id,
        hotel_id=hotel.id,
        room_type_id=room.id,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        rooms_count=rooms_count,
        price_snapshot_paise=price_paise,
        currency=room.currency,
        status="PENDING_PAYMENT",
    )
    db.add(booking)
    await db.flush()
    return booking


async def get_hotel_booking(db: AsyncSession, *, user: User, booking_id: uuid.UUID) -> HotelBooking:
    booking = await db.get(HotelBooking, booking_id)
    if booking is None:
        raise NotFoundError("Hotel booking not found.")
    if booking.user_id != user.id:
        raise PermissionDeniedError("This booking belongs to another traveller.")
    return booking


async def cancel_hotel_booking(
    db: AsyncSession, *, user: User, booking_id: uuid.UUID, reason: str | None
) -> HotelBooking:
    booking = await get_hotel_booking(db, user=user, booking_id=booking_id)
    if booking.status not in ("PENDING_PAYMENT", "CONFIRMED"):
        raise ConflictError(f"Booking in status {booking.status} cannot be cancelled.")
    booking.status = "CANCELLED"
    booking.cancelled_at = gw.utcnow()
    booking.cancellation_reason = reason
    await db.flush()
    return booking


# --------------------------------------------------------------------------- #
# guide bookings
# --------------------------------------------------------------------------- #


async def create_guide_booking(
    db: AsyncSession,
    *,
    user: User,
    guide_profile_id: uuid.UUID,
    service_start_date: date,
    service_end_date: date,
    trip_id: uuid.UUID | None,
) -> GuideBooking:
    """Guide booking gated on APPROVED + PUBLIC discovery status (§5) and
    self-declared availability (§16: a date with no row is NOT offered)."""
    await _trip_owned_or_none(db, trip_id, user)
    guide = await _guide_or_404(db, guide_profile_id)
    if guide.status != "APPROVED" or guide.visibility != "PUBLIC":
        raise ValidationError("This guide is not accepting bookings right now.")
    if guide.day_rate_paise is None:
        raise ValidationError("This guide has not published a day rate yet.")
    _validate_horizon(service_start_date, "service_start_date")
    _validate_horizon(service_end_date, "service_end_date")

    # availability: every service date needs an explicit AVAILABLE row (§16)
    n_days = (service_end_date - service_start_date).days + 1
    wanted = [service_start_date + timedelta(days=i) for i in range(n_days)]
    rows = (
        await db.execute(
            select(GuideAvailability.service_date, GuideAvailability.status)
            .where(GuideAvailability.guide_profile_id == guide.id)
            .where(GuideAvailability.service_date.in_(wanted))
        )
    ).all()
    by_date = {str(d): s for d, s in rows}
    missing = [str(d) for d in wanted if str(d) not in by_date]
    if missing:
        raise ConflictError(
            "Guide has not offered some of the requested dates "
            f"(first: {missing[0]}); pick dates the guide marked available."
        )
    busy = [d for d, s in by_date.items() if s != "AVAILABLE"]
    if busy:
        raise ConflictError(f"Guide is not available on {sorted(busy)[0]}.")

    # double-booking guard: any non-cancelled booking overlapping the range
    overlap = await db.scalar(
        select(func.count(GuideBooking.id))
        .where(GuideBooking.guide_profile_id == guide.id)
        .where(GuideBooking.status.in_(("PENDING_PAYMENT", "CONFIRMED")))
        .where(GuideBooking.service_start_date <= service_end_date)
        .where(GuideBooking.service_end_date >= service_start_date)
    )
    if overlap:
        raise ConflictError("Guide is already booked for (part of) this period.")

    days = n_days
    booking = GuideBooking(
        reference_id=gw.new_reference("GB"),
        user_id=user.id,
        trip_id=trip_id,
        guide_profile_id=guide.id,
        service_start_date=service_start_date,
        service_end_date=service_end_date,
        price_snapshot_paise=guide.day_rate_paise * days,
        currency=guide.currency,
        status="PENDING_PAYMENT",
    )
    db.add(booking)
    await db.flush()
    return booking


async def get_guide_booking(db: AsyncSession, *, user: User, booking_id: uuid.UUID) -> GuideBooking:
    booking = await db.get(GuideBooking, booking_id)
    if booking is None:
        raise NotFoundError("Guide booking not found.")
    if booking.user_id != user.id:
        raise PermissionDeniedError("This booking belongs to another traveller.")
    return booking


async def cancel_guide_booking(
    db: AsyncSession, *, user: User, booking_id: uuid.UUID, reason: str | None
) -> GuideBooking:
    booking = await get_guide_booking(db, user=user, booking_id=booking_id)
    if booking.status not in ("PENDING_PAYMENT", "CONFIRMED"):
        raise ConflictError(f"Booking in status {booking.status} cannot be cancelled.")
    booking.status = "CANCELLED"
    booking.cancelled_at = gw.utcnow()
    booking.cancellation_reason = reason
    await db.flush()
    return booking


# --------------------------------------------------------------------------- #
# payments
# --------------------------------------------------------------------------- #


async def _booking_total_for_user(
    db: AsyncSession,
    *,
    user: User,
    hotel_booking_id: uuid.UUID | None,
    guide_booking_id: uuid.UUID | None,
) -> tuple[int, str]:
    total = 0
    currency = "INR"
    if hotel_booking_id is not None:
        b = await db.get(HotelBooking, hotel_booking_id)
        if b is None or b.user_id != user.id:
            raise ValidationError("hotel_booking_id does not reference one of your bookings.")
        if b.status != "PENDING_PAYMENT":
            raise ConflictError(f"Hotel booking is already {b.status}.")
        total += b.price_snapshot_paise
        currency = b.currency
    if guide_booking_id is not None:
        b = await db.get(GuideBooking, guide_booking_id)
        if b is None or b.user_id != user.id:
            raise ValidationError("guide_booking_id does not reference one of your bookings.")
        if b.status != "PENDING_PAYMENT":
            raise ConflictError(f"Guide booking is already {b.status}.")
        total += b.price_snapshot_paise
        currency = b.currency
    return total, currency


async def create_payment(
    db: AsyncSession,
    *,
    user: User,
    hotel_booking_id: uuid.UUID | None,
    guide_booking_id: uuid.UUID | None,
    idempotency_key: str | None,
) -> Payment:
    """Create the gateway order + payments row. Idempotent on the caller's key
    (unique constraint) and on bookings already paid (status check above)."""
    total, currency = await _booking_total_for_user(
        db, user=user, hotel_booking_id=hotel_booking_id, guide_booking_id=guide_booking_id
    )

    if idempotency_key:
        existing = await db.scalar(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        if existing is not None:
            if existing.user_id != user.id:
                raise PermissionDeniedError("This idempotency key belongs to another traveller.")
            return existing  # replay: return the original payment untouched

    g = get_payment_gateway()
    receipt = f"viram-{uuid.uuid4().hex[:12]}"
    order = g.create_order(amount_paise=total, currency=currency, receipt=receipt)

    payment = Payment(
        user_id=user.id,
        hotel_booking_id=hotel_booking_id,
        guide_booking_id=guide_booking_id,
        gateway=g.name,
        gateway_order_id=order.gateway_order_id,
        amount_paise=total,
        currency=currency,
        status="CREATED",
        idempotency_key=idempotency_key or f"auto-{uuid.uuid4().hex}",
    )
    db.add(payment)
    await db.flush()
    return payment


def serialize_payment(payment: Payment) -> dict:
    return {
        "id": str(payment.id),
        "gateway": payment.gateway,
        "gateway_order_id": payment.gateway_order_id,
        "amount_paise": payment.amount_paise,
        "currency": payment.currency,
        "status": payment.status,
        "hotel_booking_id": str(payment.hotel_booking_id) if payment.hotel_booking_id else None,
        "guide_booking_id": str(payment.guide_booking_id) if payment.guide_booking_id else None,
        "mock_checkout": payment.gateway == "MOCK",  # honest labelling of the dev gateway
    }


async def confirm_mock_payment(
    db: AsyncSession, *, user: User, payment_id: uuid.UUID
) -> Payment:
    """DEV/DEMO ONLY: simulate the gateway callback for the mock gateway.

    Mirrors exactly what the real webhook path does (state transition in one
    transaction); the HTTP route exposing this is labelled mock.
    """
    payment = await db.get(Payment, payment_id)
    if payment is None or payment.user_id != user.id:
        raise NotFoundError("Payment not found.")
    if payment.gateway != "MOCK":
        raise ValidationError("Only mock-gateway payments can be simulated.")
    if payment.status in ("SUCCEEDED", "REFUNDED"):
        return payment  # idempotent re-confirm
    if payment.status == "FAILED":
        raise ConflictError("This payment already failed; create a new one.")
    await _apply_payment_success(db, payment)
    await db.flush()
    return payment


async def _apply_payment_success(db: AsyncSession, payment: Payment) -> None:
    """Single authoritative transition: payment SUCCEEDED + bookings CONFIRMED,
    in one transaction (design §18). Also derives trip status."""
    payment.status = "SUCCEEDED"
    payment.paid_at = gw.utcnow()

    trip_ids: list[uuid.UUID] = []
    if payment.hotel_booking_id is not None:
        b = await db.get(HotelBooking, payment.hotel_booking_id)
        if b is not None and b.status == "PENDING_PAYMENT":
            b.status = "CONFIRMED"
            if b.trip_id:
                trip_ids.append(b.trip_id)
    if payment.guide_booking_id is not None:
        b = await db.get(GuideBooking, payment.guide_booking_id)
        if b is not None and b.status == "PENDING_PAYMENT":
            b.status = "CONFIRMED"
            if b.trip_id:
                trip_ids.append(b.trip_id)

    from app.models.planning import Trip

    for trip_id in set(trip_ids):
        trip = await db.get(Trip, trip_id)
        if trip is not None and trip.status in ("PLANNING", "BOOKED"):
            trip.status = "BOOKED" if trip.status == "PLANNING" else trip.status


async def _apply_payment_failure(db: AsyncSession, payment: Payment, reason: str) -> None:
    """Failures cancel the linked pending bookings — never delete (§25)."""
    payment.status = "FAILED"
    if payment.hotel_booking_id is not None:
        b = await db.get(HotelBooking, payment.hotel_booking_id)
        if b is not None and b.status == "PENDING_PAYMENT":
            b.status = "CANCELLED"
            b.cancelled_at = gw.utcnow()
            b.cancellation_reason = f"payment_failed: {reason}"
    if payment.guide_booking_id is not None:
        b = await db.get(GuideBooking, payment.guide_booking_id)
        if b is not None and b.status == "PENDING_PAYMENT":
            b.status = "CANCELLED"
            b.cancelled_at = gw.utcnow()
            b.cancellation_reason = f"payment_failed: {reason}"


async def process_webhook_event(
    db: AsyncSession, *, provider: str, event_id: str, payload: dict
) -> dict:
    """Webhook ingestion: (provider, event_id) dedup keeps replays harmless
    (design §18). The gateway payload is the authority for final state."""
    import hashlib
    import uuid as uuidlib

    # dedup insert — a replay of a processed event is a no-op
    existing = await db.get(PaymentWebhookEvent, {"provider": provider, "event_id": event_id})
    if existing is not None:
        return {"deduplicated": True, "event_id": event_id}

    event = PaymentWebhookEvent(
        provider=provider, event_id=event_id, payload=payload, processed_at=gw.utcnow()
    )
    db.add(event)

    event_type = str(payload.get("event", ""))
    body = payload.get("payload", {}) if isinstance(payload.get("payload"), dict) else {}
    order_id = None
    if event_type == "payment.succeeded":
        payment_entity = body.get("payment", {})
        order_id = payment_entity.get("order_id") if isinstance(payment_entity, dict) else None
    if order_id is None:
        order_id = payload.get("order_id")

    if not order_id:
        await db.flush()
        return {"processed": True, "action": "ignored_no_order", "event_id": event_id}

    payment = await db.scalar(select(Payment).where(Payment.gateway_order_id == order_id))
    if payment is None:
        await db.flush()
        return {"processed": True, "action": "ignored_unknown_order", "event_id": event_id}

    if event_type == "payment.succeeded":
        if payment.status not in ("SUCCEEDED", "REFUNDED"):
            await _apply_payment_success(db, payment)
        action = "payment_succeeded"
    elif event_type == "payment.failed":
        if payment.status in ("CREATED", "PENDING"):
            await _apply_payment_failure(db, payment, str(payload.get("reason", "gateway failure")))
        action = "payment_failed"
    else:
        action = "ignored_unhandled_event"

    await db.flush()
    return {
        "processed": True,
        "action": action,
        "event_id": event_id,
        "payment_status": payment.status,
        "dedup_key": hashlib.sha256(f"{provider}:{event_id}".encode()).hexdigest()[:12],
        "payment_id": str(uuidlib.UUID(str(payment.id))) if payment.id else None,
    }
