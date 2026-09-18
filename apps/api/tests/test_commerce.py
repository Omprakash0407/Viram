"""Commerce flow tests: hotels, guides, bookings, payments, contact access.

Covers the rules that matter (design §15–§18, §24):
- server-side pricing (client totals never trusted)
- guide gating (APPROVED+PUBLIC only) + self-declared availability (§16)
- double-booking guard
- payment idempotency + one-transaction confirmation (PENDING_PAYMENT→CONFIRMED)
- CONDITIONAL_BOOKING_ACCESS: guide contact only after CONFIRMED, audit-logged
- ownership (IDOR) on every booking/payment read
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.models.commerce import AdminAuditLog, GuideAvailability, GuideProfile, Hotel, RoomType
from app.models.user import User


def _register(client, email: str) -> dict:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Traveller#2026", "display_name": "T"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _login(client, email: str) -> dict:
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Traveller#2026"}
    )
    assert r.status_code == 200, r.text
    return r.json()


def _auth(client, email: str) -> dict:
    tokens = _login(client, email)["tokens"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _seed_hotel() -> tuple[Hotel, RoomType]:
    from app.core.database import AsyncSessionLocal
    from app.models.geo import City, State

    async with AsyncSessionLocal() as db:
        city = await db.scalar(select(City).where(City.slug == "test-city"))
        if city is None:
            state = State(name="Test State", slug="test-state")
            db.add(state)
            await db.flush()
            city = City(
                state_id=state.id, name="Test City", slug="test-city",
                latitude=20.0, longitude=85.0,
            )
            db.add(city)
            await db.flush()
        hotel = Hotel(
            city_id=city.id, name="Test Hotel", slug="test-hotel",
            description="d", amenities=["wifi"], public_address="addr", status="ACTIVE",
        )
        db.add(hotel)
        await db.flush()
        room = RoomType(
            hotel_id=hotel.id, name="Standard", capacity=2,
            nightly_rate_paise=300_000, declared_units=5,
        )
        db.add(room)
        await db.commit()
        return hotel.id, room.id


async def _seed_guide(*, approved: bool = True, public: bool = True, rate: int | None = 250_000) -> uuid.UUID:
    from app.core.database import AsyncSessionLocal
    from app.models.geo import City, State

    async with AsyncSessionLocal() as db:
        suffix = uuid.uuid4().hex[:8]
        user = User(
            email=f"g{suffix}@x.test",
            password_hash=hash_password("Guide#2026"),
            display_name="G",
            account_role="USER",
            status="ACTIVE",
        )
        db.add(user)
        await db.flush()
        city = await db.scalar(select(City).where(City.slug == "test-city"))
        if city is None:
            state = State(name="Test State", slug="test-state")
            db.add(state)
            await db.flush()
            city = City(
                state_id=state.id, name="Test City", slug="test-city",
                latitude=20.0, longitude=85.0,
            )
            db.add(city)
            await db.flush()
        guide = GuideProfile(
            user_id=user.id, public_name=f"Guide {suffix}", bio="b",
            languages=["Odia"], expertise=["t"], areas_served=["a"],
            city_id=city.id, day_rate_paise=rate,
            status="APPROVED" if approved else "PENDING",
            visibility="PUBLIC" if public else "PRIVATE",
        )
        db.add(guide)
        await db.flush()
        today = date.today()
        for i in range(10):
            db.add(
                GuideAvailability(
                    guide_profile_id=guide.id, service_date=today + timedelta(days=i),
                    status="AVAILABLE",
                )
            )
        await db.commit()
        return guide.id


# --------------------------------------------------------------------------- #
# hotels & bookings
# --------------------------------------------------------------------------- #


def test_hotel_booking_server_sides_the_price(client):
    import asyncio

    hotel_id, room_id = asyncio.run(_seed_hotel())
    _register(client, "hb1@test.com")
    hdrs = _auth(client, "hb1@test.com")

    check_in = date.today() + timedelta(days=3)
    check_out = check_in + timedelta(days=2)  # 2 nights
    r = client.post(
        "/api/v1/hotel-bookings",
        headers=hdrs,
        json={
            "hotel_id": str(hotel_id),
            "room_type_id": str(room_id),
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rooms_count": 2,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # 300000 paise * 2 nights * 2 rooms — computed server-side, not from client
    assert body["amount_paise"] == 1_200_000
    assert body["status"] == "PENDING_PAYMENT"
    assert body["reference_id"].startswith("VIR-HB-")


def test_hotel_booking_rejects_bad_dates(client):
    import asyncio

    hotel_id, room_id = asyncio.run(_seed_hotel())
    _register(client, "hb2@test.com")
    hdrs = _auth(client, "hb2@test.com")

    r = client.post(
        "/api/v1/hotel-bookings",
        headers=hdrs,
        json={
            "hotel_id": str(hotel_id),
            "room_type_id": str(room_id),
            "check_in_date": date.today().isoformat(),
            "check_out_date": date.today().isoformat(),  # same day → invalid
            "rooms_count": 1,
        },
    )
    assert r.status_code == 422

    r = client.post(
        "/api/v1/hotel-bookings",
        headers=hdrs,
        json={
            "hotel_id": str(hotel_id),
            "room_type_id": str(room_id),
            "check_in_date": (date.today() - timedelta(days=1)).isoformat(),  # past
            "check_out_date": date.today().isoformat(),
            "rooms_count": 1,
        },
    )
    assert r.status_code == 422


def test_hotel_booking_ownership_idor_blocked(client):
    import asyncio

    hotel_id, room_id = asyncio.run(_seed_hotel())
    _register(client, "hb3a@test.com")
    _register(client, "hb3b@test.com")
    a = _auth(client, "hb3a@test.com")
    b = _auth(client, "hb3b@test.com")

    r = client.post(
        "/api/v1/hotel-bookings",
        headers=a,
        json={
            "hotel_id": str(hotel_id), "room_type_id": str(room_id),
            "check_in_date": (date.today() + timedelta(days=1)).isoformat(),
            "check_out_date": (date.today() + timedelta(days=2)).isoformat(),
            "rooms_count": 1,
        },
    )
    booking_id = r.json()["id"]

    # other user cannot read it
    r = client.get(f"/api/v1/hotel-bookings/{booking_id}", headers=b)
    assert r.status_code == 403
    # owner can
    r = client.get(f"/api/v1/hotel-bookings/{booking_id}", headers=a)
    assert r.status_code == 200


# --------------------------------------------------------------------------- #
# guides & guide bookings
# --------------------------------------------------------------------------- #


def test_guide_discovery_requires_approved_public(client):
    import asyncio

    asyncio.run(_seed_guide(approved=False))  # pending → hidden
    asyncio.run(_seed_guide())  # approved+public → visible
    _register(client, "gd1@test.com")
    hdrs = _auth(client, "gd1@test.com")

    r = client.get("/api/v1/guides", headers=hdrs)
    assert r.status_code == 200
    names = [g["public_name"] for g in r.json()["items"]]
    assert len(names) == 1  # only the approved/public one


def test_guide_booking_gated_on_verification(client):
    import asyncio

    pending = asyncio.run(_seed_guide(approved=False))
    _register(client, "gd2@test.com")
    hdrs = _auth(client, "gd2@test.com")

    d = (date.today() + timedelta(days=2)).isoformat()
    r = client.post(
        "/api/v1/guide-bookings",
        headers=hdrs,
        json={"guide_profile_id": str(pending), "service_start_date": d, "service_end_date": d},
    )
    assert r.status_code == 422  # not APPROVED+PUBLIC → not bookable


def test_guide_booking_requires_declared_availability(client):
    import asyncio

    guide_id = asyncio.run(_seed_guide())
    _register(client, "gd3@test.com")
    hdrs = _auth(client, "gd3@test.com")

    # date beyond the 10 seeded available days → no row → not offered (§16)
    far = (date.today() + timedelta(days=40)).isoformat()
    r = client.post(
        "/api/v1/guide-bookings",
        headers=hdrs,
        json={"guide_profile_id": str(guide_id), "service_start_date": far, "service_end_date": far},
    )
    assert r.status_code == 409

    # a declared available day books fine
    ok = (date.today() + timedelta(days=2)).isoformat()
    r = client.post(
        "/api/v1/guide-bookings",
        headers=hdrs,
        json={"guide_profile_id": str(guide_id), "service_start_date": ok, "service_end_date": ok},
    )
    assert r.status_code == 201, r.text
    assert r.json()["amount_paise"] == 250_000  # 1 day at the seeded rate


def test_guide_double_booking_blocked(client):
    import asyncio

    guide_id = asyncio.run(_seed_guide())
    _register(client, "gd4a@test.com")
    _register(client, "gd4b@test.com")
    a = _auth(client, "gd4a@test.com")
    b = _auth(client, "gd4b@test.com")
    d1 = (date.today() + timedelta(days=2)).isoformat()
    d2 = (date.today() + timedelta(days=3)).isoformat()

    r = client.post(
        "/api/v1/guide-bookings", headers=a,
        json={"guide_profile_id": str(guide_id), "service_start_date": d1, "service_end_date": d2},
    )
    assert r.status_code == 201
    # overlapping window (d2 overlaps [d1, d2]) from a different user → conflict
    r = client.post(
        "/api/v1/guide-bookings", headers=b,
        json={"guide_profile_id": str(guide_id), "service_start_date": d2, "service_end_date": d2},
    )
    assert r.status_code == 409


# --------------------------------------------------------------------------- #
# payments
# --------------------------------------------------------------------------- #


def _book_one_night(client, hdrs, hotel_id, room_id) -> str:
    r = client.post(
        "/api/v1/hotel-bookings", headers=hdrs,
        json={
            "hotel_id": str(hotel_id), "room_type_id": str(room_id),
            "check_in_date": (date.today() + timedelta(days=5)).isoformat(),
            "check_out_date": (date.today() + timedelta(days=6)).isoformat(),
            "rooms_count": 1,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_payment_confirms_booking_in_one_flow(client):
    import asyncio

    hotel_id, room_id = asyncio.run(_seed_hotel())
    _register(client, "pay1@test.com")
    hdrs = _auth(client, "pay1@test.com")
    booking_id = _book_one_night(client, hdrs, hotel_id, room_id)

    r = client.post(
        "/api/v1/payments", headers=hdrs,
        json={"hotel_booking_id": booking_id, "idempotency_key": "idem-1"},
    )
    assert r.status_code == 201, r.text
    payment = r.json()
    assert payment["amount_paise"] == 300_000
    assert payment["gateway"] == "MOCK"
    assert payment["mock_checkout"] is True  # honest labelling

    # idempotent replay returns the same payment
    r2 = client.post(
        "/api/v1/payments", headers=hdrs,
        json={"hotel_booking_id": booking_id, "idempotency_key": "idem-1"},
    )
    assert r2.status_code == 201
    assert r2.json()["id"] == payment["id"]

    # mock-confirm simulates the gateway success → booking CONFIRMED
    r = client.post(f"/api/v1/payments/{payment['id']}/mock-confirm", headers=hdrs)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "SUCCEEDED"

    r = client.get(f"/api/v1/hotel-bookings/{booking_id}", headers=hdrs)
    assert r.json()["status"] == "CONFIRMED"


def test_payment_rejects_double_payment_of_confirmed_booking(client):
    import asyncio

    hotel_id, room_id = asyncio.run(_seed_hotel())
    _register(client, "pay2@test.com")
    hdrs = _auth(client, "pay2@test.com")
    booking_id = _book_one_night(client, hdrs, hotel_id, room_id)

    p1 = client.post("/api/v1/payments", headers=hdrs, json={"hotel_booking_id": booking_id}).json()
    client.post(f"/api/v1/payments/{p1['id']}/mock-confirm", headers=hdrs)

    r = client.post("/api/v1/payments", headers=hdrs, json={"hotel_booking_id": booking_id})
    assert r.status_code == 409


def test_payment_ownership_idor_blocked(client):
    import asyncio

    hotel_id, room_id = asyncio.run(_seed_hotel())
    _register(client, "pay3a@test.com")
    _register(client, "pay3b@test.com")
    a = _auth(client, "pay3a@test.com")
    b = _auth(client, "pay3b@test.com")
    booking_id = _book_one_night(client, a, hotel_id, room_id)

    # b cannot create a payment for a's booking
    r = client.post("/api/v1/payments", headers=b, json={"hotel_booking_id": booking_id})
    assert r.status_code == 422
    # b cannot confirm a's payment
    p = client.post("/api/v1/payments", headers=a, json={"hotel_booking_id": booking_id}).json()
    r = client.post(f"/api/v1/payments/{p['id']}/mock-confirm", headers=b)
    assert r.status_code == 404


def test_webhook_signature_enforced_and_deduplicated(client):
    from app.core.config import settings
    import hashlib
    import hmac as hmac_mod
    import json as json_mod

    _register(client, "wh1@test.com")
    payload = {
        "event_id": "evt_123",
        "event": "payment.succeeded",
        "order_id": "order_does_not_exist",
        "payload": {"payment": {"order_id": "order_does_not_exist"}},
    }
    body = json_mod.dumps(payload).encode()

    # bad signature rejected
    r = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Signature": "deadbeef"},
    )
    assert r.status_code == 403

    # valid signature accepted; unknown order recorded but ignored
    sig = hmac_mod.new(settings.MOCK_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    r = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert r.status_code == 202, r.text
    assert r.json()["action"] == "ignored_unknown_order"

    # replay of the same event_id is deduplicated
    r = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert r.status_code == 202
    assert r.json().get("deduplicated") is True


def test_webhook_success_flips_booking(client):
    import asyncio
    import hashlib
    import hmac as hmac_mod
    import json as json_mod

    from app.core.config import settings

    hotel_id, room_id = asyncio.run(_seed_hotel())
    _register(client, "wh2@test.com")
    hdrs = _auth(client, "wh2@test.com")
    booking_id = _book_one_night(client, hdrs, hotel_id, room_id)

    payment = client.post(
        "/api/v1/payments", headers=hdrs, json={"hotel_booking_id": booking_id}
    ).json()

    payload = {
        "event_id": f"evt_{payment['gateway_order_id']}",
        "event": "payment.succeeded",
        "payload": {"payment": {"order_id": payment["gateway_order_id"]}},
    }
    body = json_mod.dumps(payload).encode()
    sig = hmac_mod.new(settings.MOCK_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    r = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert r.status_code == 202
    assert r.json()["action"] == "payment_succeeded"

    r = client.get(f"/api/v1/hotel-bookings/{booking_id}", headers=hdrs)
    assert r.json()["status"] == "CONFIRMED"


# --------------------------------------------------------------------------- #
# conditional contact access (§24)
# --------------------------------------------------------------------------- #


def test_guide_contact_released_only_after_confirmation(client):
    import asyncio

    guide_id = asyncio.run(_seed_guide())
    _register(client, "ct1@test.com")
    hdrs = _auth(client, "ct1@test.com")
    d = (date.today() + timedelta(days=2)).isoformat()

    r = client.post(
        "/api/v1/guide-bookings", headers=hdrs,
        json={"guide_profile_id": str(guide_id), "service_start_date": d, "service_end_date": d},
    )
    booking_id = r.json()["id"]

    # before payment: contact withheld
    r = client.get(f"/api/v1/guide-bookings/{booking_id}", headers=hdrs)
    assert r.status_code == 200
    assert r.json()["guide_contact"] is None
    assert "confirmed" in r.json()["guide_contact_note"].lower()

    # pay + confirm
    p = client.post(
        "/api/v1/payments", headers=hdrs, json={"guide_booking_id": booking_id}
    ).json()
    client.post(f"/api/v1/payments/{p['id']}/mock-confirm", headers=hdrs)

    # after confirmation: contact released
    r = client.get(f"/api/v1/guide-bookings/{booking_id}", headers=hdrs)
    contact = r.json()["guide_contact"]
    assert contact is not None
    assert contact["email"] == "guide.puri@viramdemo.com" or contact["email"].endswith("@x.test")

    # ...and the release is audit-logged
    async def _check_audit():
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            rows = (
                await db.scalars(
                    select(AdminAuditLog).where(AdminAuditLog.action == "CONTACT_ACCESSED")
                )
            ).all()
            return len(rows)

    assert asyncio.run(_check_audit()) >= 1


def test_trip_bookings_aggregation_ownership(client):
    import asyncio

    from app.core.database import AsyncSessionLocal
    from app.models.geo import City
    from app.models.planning import Trip

    async def _mk_trip(user_id):
        async with AsyncSessionLocal() as db:
            from app.models.geo import State

            city = await db.scalar(select(City).where(City.slug == "test-city"))
            if city is None:
                state = State(name="Test State", slug="test-state")
                db.add(state)
                await db.flush()
                city = City(
                    state_id=state.id, name="Test City", slug="test-city",
                    latitude=20.0, longitude=85.0,
                )
                db.add(city)
                await db.flush()
            trip = Trip(
                user_id=user_id, city_id=city.id,
                starts_on=date.today() + timedelta(days=7),
                ends_on=date.today() + timedelta(days=9),
                party_size=2, status="PLANNING", preferences_snapshot={},
            )
            db.add(trip)
            await db.commit()
            return trip.id

    hotel_id, room_id = asyncio.run(_seed_hotel())
    _register(client, "tb1@test.com")
    hdrs = _auth(client, "tb1@test.com")

    # need the user id → from /users/me
    me = client.get("/api/v1/users/me", headers=hdrs).json()
    trip_id = asyncio.run(_mk_trip(uuid.UUID(me["id"])))

    _register(client, "tb2@test.com")
    other = _auth(client, "tb2@test.com")
    r = client.get(f"/api/v1/trips/{trip_id}/bookings", headers=other)
    assert r.status_code == 403  # someone else's trip

    r = client.get(f"/api/v1/trips/{trip_id}/bookings", headers=hdrs)
    assert r.status_code == 200
    assert r.json()["hotel_bookings"] == []
