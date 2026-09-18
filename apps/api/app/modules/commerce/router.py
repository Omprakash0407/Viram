"""Commerce endpoints: hotel/guide discovery + bookings + payments.

Security posture (design §24):
- Every booking/payment route derives identity from the JWT — never the client.
- Ownership is enforced on every read/cancel of a booking.
- Guide private contact is CONDITIONAL_BOOKING_ACCESS: released only for a
  CONFIRMED booking owned by the caller, and the access is audit-logged.
"""

import uuid

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.exceptions import ValidationError
from app.models.commerce import (
    AdminAuditLog,
    GuideAvailability,
    GuideBooking,
    GuideProfile,
    Hotel,
    HotelBooking,
    Payment,
    RoomType,
)
from app.models.user import User
from app.modules.commerce import gateway as gw
from app.modules.commerce import service
from app.modules.commerce.schemas import (
    GuideBookingCreate,
    HotelBookingCreate,
    PaymentCreate,
)
from app.modules.users.deps import get_current_user

router = APIRouter(tags=["commerce"])

WEBHOOK_UNAUTHENTICATED_NOTE = (
    "Gateway-to-gateway callback; authenticated by HMAC signature instead of a bearer token (§18)."
)


def _paise(amount: int, currency: str) -> dict:
    return {"amount_paise": amount, "currency": currency}


def _hotel_out(h: Hotel) -> dict:
    return {
        "id": str(h.id),
        "name": h.name,
        "slug": h.slug,
        "description": h.description,
        "amenities": h.amenities,
        "public_phone": h.public_phone,
        "public_address": h.public_address,
        "city_id": str(h.city_id),
    }


def _room_out(r: RoomType) -> dict:
    return {
        "id": str(r.id),
        "hotel_id": str(r.hotel_id),
        "name": r.name,
        "capacity": r.capacity,
        "nightly_rate_paise": r.nightly_rate_paise,
        "currency": r.currency,
        "declared_units": r.declared_units,
        "availability_note": "Request-based booking; not a live inventory guarantee (design D6).",
    }


def _guide_out(g: GuideProfile, city_name: str | None) -> dict:
    return {
        "id": str(g.id),
        "public_name": g.public_name,
        "bio": g.bio,
        "languages": g.languages,
        "expertise": g.expertise,
        "areas_served": g.areas_served,
        "city_id": str(g.city_id) if g.city_id else None,
        "city_name": city_name,
        "day_rate_paise": g.day_rate_paise,
        "currency": g.currency,
        "review_rating": None,  # ratings arrive with the reviews phase (§12)
    }


# --------------------------------------------------------------------------- #
# discovery (public-ish: auth kept for consistency with the wizard context)
# --------------------------------------------------------------------------- #


@router.get("/hotels")
async def list_hotels(
    city_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(Hotel).where(Hotel.status == "ACTIVE")
    if city_id is not None:
        stmt = stmt.where(Hotel.city_id == city_id)
    hotels = list((await db.scalars(stmt.order_by(Hotel.name))).all())
    return {"items": [_hotel_out(h) for h in hotels]}


@router.get("/hotels/{hotel_id}/rooms")
async def list_room_types(
    hotel_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    hotel = await db.get(Hotel, hotel_id)
    if hotel is None or hotel.status != "ACTIVE":
        raise NotFoundError("Hotel not found.")
    rooms = list(
        (
            await db.scalars(
                select(RoomType).where(RoomType.hotel_id == hotel.id).order_by(RoomType.nightly_rate_paise)
            )
        ).all()
    )
    return {"hotel": _hotel_out(hotel), "items": [_room_out(r) for r in rooms]}


@router.get("/guides")
async def list_guides(
    city_id: uuid.UUID | None = None,
    service_date: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Discovery exposes only APPROVED + PUBLIC guides (§5, partial index)."""
    from datetime import date as date_cls

    stmt = select(GuideProfile).where(
        GuideProfile.status == "APPROVED", GuideProfile.visibility == "PUBLIC"
    )
    if city_id is not None:
        stmt = stmt.where(GuideProfile.city_id == city_id)
    guides = list((await db.scalars(stmt.order_by(GuideProfile.public_name))).all())

    offered: dict[uuid.UUID, list[str]] = {}
    if service_date:
        try:
            d = date_cls.fromisoformat(service_date)
        except ValueError as exc:
            raise ValidationError("service_date must be ISO format YYYY-MM-DD.") from exc
        rows = (
            await db.scalars(
                select(GuideAvailability).where(
                    GuideAvailability.service_date == d, GuideAvailability.status == "AVAILABLE"
                )
            )
        ).all()
        offered = {r.guide_profile_id: [service_date] for r in rows}
        guides = [g for g in guides if g.id in offered]

    city_names: dict[uuid.UUID, str] = {}
    if guides:
        from app.models.geo import City

        city_ids = {g.city_id for g in guides if g.city_id}
        if city_ids:
            for c in (await db.scalars(select(City).where(City.id.in_(city_ids)))).all():
                city_names[c.id] = c.name

    return {
        "items": [
            {**_guide_out(g, city_names.get(g.city_id)), "offered_on": offered.get(g.id)}
            for g in guides
        ]
    }


@router.get("/guides/{guide_profile_id}/availability")
async def guide_availability(
    guide_profile_id: uuid.UUID,
    month: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Self-declared availability for a month (YYYY-MM): dates the guide
    explicitly offered. Dates absent here are NOT bookable (§16)."""
    from datetime import date as date_cls

    try:
        year, mon = (int(p) for p in month.split("-"))
        first = date_cls(year, mon, 1)
    except (ValueError, TypeError) as exc:
        raise ValidationError("month must be YYYY-MM.") from exc
    if mon == 12:
        nxt = date_cls(year + 1, 1, 1)
    else:
        nxt = date_cls(year, mon + 1, 1)

    guide = await service._guide_or_404(db, guide_profile_id)
    rows = (
        await db.scalars(
            select(GuideAvailability)
            .where(GuideAvailability.guide_profile_id == guide.id)
            .where(GuideAvailability.service_date >= first)
            .where(GuideAvailability.service_date < nxt)
        )
    ).all()
    return {
        "guide_profile_id": str(guide.id),
        "month": month,
        "available_dates": [r.service_date.isoformat() for r in rows if r.status == "AVAILABLE"],
        "unavailable_dates": [r.service_date.isoformat() for r in rows if r.status != "AVAILABLE"],
        "note": "Dates without a row are not offered by the guide (design §16).",
    }


# --------------------------------------------------------------------------- #
# hotel bookings (OWNER_ONLY)
# --------------------------------------------------------------------------- #


@router.post("/hotel-bookings", status_code=status.HTTP_201_CREATED)
async def create_hotel_booking(
    payload: HotelBookingCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    b = await service.create_hotel_booking(
        db,
        user=user,
        hotel_id=payload.hotel_id,
        room_type_id=payload.room_type_id,
        check_in_date=payload.check_in_date,
        check_out_date=payload.check_out_date,
        rooms_count=payload.rooms_count,
        trip_id=payload.trip_id,
    )
    await db.commit()
    return {
        "id": str(b.id),
        "reference_id": b.reference_id,
        "status": b.status,
        "check_in_date": b.check_in_date.isoformat(),
        "check_out_date": b.check_out_date.isoformat(),
        "rooms_count": b.rooms_count,
        **_paise(b.price_snapshot_paise, b.currency),
    }


@router.get("/hotel-bookings")
async def list_hotel_bookings(
    trip_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(HotelBooking).where(HotelBooking.user_id == user.id)
    if trip_id is not None:
        stmt = stmt.where(HotelBooking.trip_id == trip_id)
    rows = list((await db.scalars(stmt.order_by(HotelBooking.created_at.desc()))).all())
    hotel_ids = {b.hotel_id for b in rows}
    hotels = {
        h.id: h
        for h in (
            await db.scalars(select(Hotel).where(Hotel.id.in_(hotel_ids)))
        ).all()
    } if hotel_ids else {}
    return {
        "items": [
            {
                "id": str(b.id),
                "reference_id": b.reference_id,
                "status": b.status,
                "hotel_name": hotels[b.hotel_id].name if b.hotel_id in hotels else None,
                "check_in_date": b.check_in_date.isoformat(),
                "check_out_date": b.check_out_date.isoformat(),
                "rooms_count": b.rooms_count,
                **_paise(b.price_snapshot_paise, b.currency),
            }
            for b in rows
        ]
    }


@router.get("/hotel-bookings/{booking_id}")
async def get_hotel_booking(
    booking_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    b = await service.get_hotel_booking(db, user=user, booking_id=booking_id)
    hotel = await db.get(Hotel, b.hotel_id)
    return {
        "id": str(b.id),
        "reference_id": b.reference_id,
        "status": b.status,
        "hotel": _hotel_out(hotel) if hotel else None,
        "check_in_date": b.check_in_date.isoformat(),
        "check_out_date": b.check_out_date.isoformat(),
        "rooms_count": b.rooms_count,
        **_paise(b.price_snapshot_paise, b.currency),
    }


class CancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


@router.post("/hotel-bookings/{booking_id}/cancel")
async def cancel_hotel_booking(
    booking_id: uuid.UUID,
    payload: CancelRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    b = await service.cancel_hotel_booking(db, user=user, booking_id=booking_id, reason=payload.reason)
    await db.commit()
    return {"id": str(b.id), "status": b.status}


# --------------------------------------------------------------------------- #
# guide bookings (OWNER_ONLY + conditional contact)
# --------------------------------------------------------------------------- #


@router.post("/guide-bookings", status_code=status.HTTP_201_CREATED)
async def create_guide_booking(
    payload: GuideBookingCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    b = await service.create_guide_booking(
        db,
        user=user,
        guide_profile_id=payload.guide_profile_id,
        service_start_date=payload.service_start_date,
        service_end_date=payload.service_end_date,
        trip_id=payload.trip_id,
    )
    await db.commit()
    return {
        "id": str(b.id),
        "reference_id": b.reference_id,
        "status": b.status,
        "service_start_date": b.service_start_date.isoformat(),
        "service_end_date": b.service_end_date.isoformat(),
        **_paise(b.price_snapshot_paise, b.currency),
    }


@router.get("/guide-bookings")
async def list_guide_bookings(
    trip_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(GuideBooking).where(GuideBooking.user_id == user.id)
    if trip_id is not None:
        stmt = stmt.where(GuideBooking.trip_id == trip_id)
    rows = list((await db.scalars(stmt.order_by(GuideBooking.created_at.desc()))).all())
    guide_ids = {b.guide_profile_id for b in rows}
    guides = {
        g.id: g
        for g in (await db.scalars(select(GuideProfile).where(GuideProfile.id.in_(guide_ids)))).all()
    } if guide_ids else {}
    return {
        "items": [
            {
                "id": str(b.id),
                "reference_id": b.reference_id,
                "status": b.status,
                "guide_name": guides[b.guide_profile_id].public_name if b.guide_profile_id in guides else None,
                "service_start_date": b.service_start_date.isoformat(),
                "service_end_date": b.service_end_date.isoformat(),
                **_paise(b.price_snapshot_paise, b.currency),
                "guide_contact_released": b.status == "CONFIRMED",
            }
            for b in rows
        ]
    }


@router.get("/guide-bookings/{booking_id}")
async def get_guide_booking(
    booking_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    b = await service.get_guide_booking(db, user=user, booking_id=booking_id)
    guide = await db.get(GuideProfile, b.guide_profile_id)
    out = {
        "id": str(b.id),
        "reference_id": b.reference_id,
        "status": b.status,
        "guide_name": guide.public_name if guide else None,
        "service_start_date": b.service_start_date.isoformat(),
        "service_end_date": b.service_end_date.isoformat(),
        **_paise(b.price_snapshot_paise, b.currency),
    }
    if b.status == "CONFIRMED":
        out["guide_contact"] = await _release_guide_contact(db, user=user, guide=guide)
        await db.commit()  # the CONTACT_ACCESSED audit row must survive this GET
    else:
        out["guide_contact"] = None
        out["guide_contact_note"] = (
            "The guide's private contact is released once the booking is confirmed (paid)."
        )
    return out


async def _release_guide_contact(
    db: AsyncSession, *, user: User, guide: GuideProfile
) -> dict | None:
    """CONDITIONAL_BOOKING_ACCESS (§24): the guide's private contact is the
    guide user's own account data; released only behind a CONFIRMED booking.
    The release is audit-logged (CONTACT_ACCESSED)."""
    if guide is None:
        return None
    guide_user = await db.get(User, guide.user_id)
    if guide_user is None:
        return None
    contact = {"name": guide.public_name, "email": guide_user.email}
    profile_phone = getattr(guide_user, "phone", None)
    if profile_phone:
        contact["phone"] = profile_phone

    db.add(
        AdminAuditLog(
            admin_id=user.id,  # accessor of the protected data
            action="CONTACT_ACCESSED",
            target_type="guide_profiles",
            target_id=guide.id,
            after={"booking_state": "CONFIRMED", "via": "guide_booking_detail"},
        )
    )
    await db.flush()
    return contact


@router.post("/guide-bookings/{booking_id}/cancel")
async def cancel_guide_booking(
    booking_id: uuid.UUID,
    payload: CancelRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    b = await service.cancel_guide_booking(db, user=user, booking_id=booking_id, reason=payload.reason)
    await db.commit()
    return {"id": str(b.id), "status": b.status}


# --------------------------------------------------------------------------- #
# payments
# --------------------------------------------------------------------------- #


@router.post("/payments", status_code=status.HTTP_201_CREATED)
async def create_payment(
    payload: PaymentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    payment = await service.create_payment(
        db,
        user=user,
        hotel_booking_id=payload.hotel_booking_id,
        guide_booking_id=payload.guide_booking_id,
        idempotency_key=payload.idempotency_key,
    )
    await db.commit()
    return service.serialize_payment(payment)


@router.get("/payments/{payment_id}")
async def get_payment(
    payment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    payment = await db.get(Payment, payment_id)
    if payment is None or payment.user_id != user.id:
        raise NotFoundError("Payment not found.")
    return service.serialize_payment(payment)


@router.post("/payments/{payment_id}/mock-confirm")
async def mock_confirm_payment(
    payment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """DEV/DEMO ONLY — simulate the gateway success callback (mock gateway).
    In production this route is never registered; the webhook is authoritative."""
    from app.core.config import settings

    if not settings.is_local:
        raise NotFoundError("Not available in this environment.")
    payment = await service.confirm_mock_payment(db, user=user, payment_id=payment_id)
    await db.commit()
    out = service.serialize_payment(payment)
    out["note"] = "Simulated via the clearly-labelled MOCK gateway; the webhook path remains authoritative."
    return out


@router.post("/payments/webhook", status_code=status.HTTP_202_ACCEPTED)
async def payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Gateway webhook — authoritative for final payment state (§18).

    Authenticated by HMAC signature (X-Signature header) instead of a bearer
    token. (provider, event_id) deduplication makes replays harmless.
    """
    body = await request.body()
    signature = request.headers.get("x-signature", "")
    g = gw.get_payment_gateway()
    if not g.verify_webhook_signature(payload_body=body, signature=signature):
        raise PermissionDeniedError("Invalid webhook signature.")

    try:
        payload = await request.json()
    except Exception as exc:  # malformed body
        raise ValidationError("Webhook payload must be valid JSON.") from exc

    event_id = str(payload.get("event_id") or uuid.uuid4())
    result = await service.process_webhook_event(
        db, provider=g.name, event_id=event_id, payload=payload
    )
    await db.commit()
    return result


@router.get("/trips/{trip_id}/bookings")
async def trip_bookings(
    trip_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Wizard Step-3 aggregation: both typed bookings for one owned trip."""
    from app.models.planning import Trip

    trip = await db.get(Trip, trip_id)
    if trip is None or trip.user_id != user.id:
        raise PermissionDeniedError("This trip belongs to another traveller.")

    hotels = list(
        (
            await db.scalars(
                select(HotelBooking)
                .where(HotelBooking.trip_id == trip_id, HotelBooking.user_id == user.id)
                .order_by(HotelBooking.created_at.desc())
            )
        ).all()
    )
    guides = list(
        (
            await db.scalars(
                select(GuideBooking)
                .where(GuideBooking.trip_id == trip_id, GuideBooking.user_id == user.id)
                .order_by(GuideBooking.created_at.desc())
            )
        ).all()
    )
    hotel_names = {
        h.id: h.name
        for h in (
            await db.scalars(select(Hotel).where(Hotel.id.in_({b.hotel_id for b in hotels})))
        ).all()
    } if hotels else {}
    guide_names = {
        g.id: g.public_name
        for g in (
            await db.scalars(
                select(GuideProfile).where(GuideProfile.id.in_({b.guide_profile_id for b in guides}))
            )
        ).all()
    } if guides else {}

    return {
        "trip_id": str(trip_id),
        "trip_status": trip.status,
        "hotel_bookings": [
            {
                "id": str(b.id),
                "reference_id": b.reference_id,
                "status": b.status,
                "hotel_name": hotel_names.get(b.hotel_id),
                "check_in_date": b.check_in_date.isoformat(),
                "check_out_date": b.check_out_date.isoformat(),
                "rooms_count": b.rooms_count,
                **_paise(b.price_snapshot_paise, b.currency),
            }
            for b in hotels
        ],
        "guide_bookings": [
            {
                "id": str(b.id),
                "reference_id": b.reference_id,
                "status": b.status,
                "guide_name": guide_names.get(b.guide_profile_id),
                "service_start_date": b.service_start_date.isoformat(),
                "service_end_date": b.service_end_date.isoformat(),
                **_paise(b.price_snapshot_paise, b.currency),
            }
            for b in guides
        ],
    }
