"""Safe-travel SOS endpoint tests (Phase 8c).

The SOS endpoint composes admin-managed safety data (§29) with the OSRM route
provider (§28) behind the live-location membership gate. The suite is hermetic
(viram_test, truncated per test), so each test seeds its own state/city and
safety rows via the same ORM models. These tests never depend on the external
router succeeding: when OSRM is unreachable the endpoint must still return
contacts + facilities with an honest route.unavailable=True — an SOS panel
cannot break because a routing vendor did.
"""

from __future__ import annotations

import asyncio
import time
import uuid


from app.models.geo import City, State
from app.models.intelligence import EmergencyContact, EmergencyFacility


def _register(client, email: str, name: str = "T") -> dict:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Traveller#2026", "display_name": name},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_safety_city() -> str:
    """One state + city + a 24x7 hospital and a police post + national numbers."""
    # Imported INSIDE the helper: conftest swaps AsyncSessionLocal onto the test
    # engine before tests run, so a module-level import would bind the original
    # (dev) engine and leak connections across loops.
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        state = State(name=f"Test State {uuid.uuid4().hex[:8]}", slug=f"test-state-{uuid.uuid4().hex[:8]}")
        db.add(state)
        await db.flush()
        city = City(
            state_id=state.id,
            name="Test City",
            slug=f"test-city-{uuid.uuid4().hex[:8]}",
            latitude=19.805,
            longitude=85.82,
        )
        db.add(city)
        await db.flush()
        db.add_all(
            [
                EmergencyFacility(
                    city_id=city.id,
                    name="Test District Hospital",
                    kind="HOSPITAL",
                    address="Hospital Road",
                    phone="06752222222",
                    is_24x7=True,
                    latitude=19.810,
                    longitude=85.825,
                ),
                EmergencyFacility(
                    city_id=city.id,
                    name="Test Police Post",
                    kind="POLICE",
                    phone="06752333333",
                    is_24x7=False,
                    latitude=19.85,
                    longitude=85.90,
                ),
                EmergencyContact(scope="NATIONAL", label="Emergency (All-in-One)", phone="112"),
                EmergencyContact(scope="NATIONAL", label="Ambulance", phone="108"),
            ]
        )
        await db.commit()
        return str(city.id)


def _make_trip(client, token: str, city_id: str) -> dict:
    r = client.post(
        "/api/v1/trips",
        headers=_auth(token),
        json={
            "city_id": city_id,
            "starts_on": "2026-10-05",
            "ends_on": "2026-10-08",
            "party_size": 2,
            "moods": ["NATURE_RELAXATION"],
            "budget_tier": "MODERATE",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_sos_requires_auth(client):
    r = client.get("/api/v1/trips/00000000-0000-0000-0000-000000000000/sos")
    assert r.status_code == 401


def test_sos_forbidden_for_non_member(client):
    t = int(time.time())
    head = _register(client, f"sos-a{t}@vtest.com")
    outsider = _register(client, f"sos-b{t}@vtest.com")
    city_id = asyncio.run(_seed_safety_city())
    trip = _make_trip(client, head["tokens"]["access_token"], city_id)
    r = client.get(
        f"/api/v1/trips/{trip['id']}/sos",
        headers=_auth(outsider["tokens"]["access_token"]),
    )
    assert r.status_code == 403


def test_sos_member_gets_contacts_and_facilities(client):
    t = int(time.time())
    head = _register(client, f"sos-c{t}@vtest.com")
    city_id = asyncio.run(_seed_safety_city())
    trip = _make_trip(client, head["tokens"]["access_token"], city_id)
    r = client.get(
        f"/api/v1/trips/{trip['id']}/sos", headers=_auth(head["tokens"]["access_token"])
    )
    assert r.status_code == 200, r.text
    body = r.json()

    # National emergency numbers always present (112 / 108 seeded above).
    assert {c["phone"] for c in body["contacts"]} >= {"112", "108"}
    # Facilities expose call-capable, mappable fields.
    kinds = {f["kind"] for f in body["facilities"]}
    assert "HOSPITAL" in kinds
    for f in body["facilities"]:
        assert {"name", "kind", "latitude", "longitude", "is_24x7"} <= set(f)


def test_sos_honest_without_live_location(client):
    """No sharing on the trip => route is None, but contacts still served."""
    t = int(time.time())
    head = _register(client, f"sos-d{t}@vtest.com")
    city_id = asyncio.run(_seed_safety_city())
    trip = _make_trip(client, head["tokens"]["access_token"], city_id)
    body = client.get(
        f"/api/v1/trips/{trip['id']}/sos", headers=_auth(head["tokens"]["access_token"])
    ).json()
    assert body["route"] is None
    assert body["reference"] is None
    assert {c["phone"] for c in body["contacts"]} >= {"112"}


def test_sos_route_from_live_location(client):
    """Sharing a position => the nearest hospital is chosen; the route is either
    a real driving route or an honest unavailable marker (never fabricated)."""
    t = int(time.time())
    head = _register(client, f"sos-e{t}@vtest.com", "SOS Head")
    tok = head["tokens"]["access_token"]
    city_id = asyncio.run(_seed_safety_city())
    trip = _make_trip(client, tok, city_id)
    r = client.put(
        f"/api/v1/trips/{trip['id']}/location",
        headers=_auth(tok),
        json={"latitude": 19.805, "longitude": 85.82, "accuracy_m": 25},
    )
    assert r.status_code == 200, r.text

    body = client.get(f"/api/v1/trips/{trip['id']}/sos", headers=_auth(tok)).json()
    assert body["reference"] is not None
    assert body["reference"]["latitude"] == 19.805
    route = body["route"]
    assert route is not None
    assert route["to"]["name"] == "Test District Hospital"  # nearest, and a HOSPITAL
    assert route["straight_line_km"] >= 0
    if route.get("unavailable"):
        assert route["distance_km"] is None  # provider down => labelled, not faked
    else:
        assert route["distance_km"] is not None and route["distance_km"] > 0
        assert route["duration_min"] is not None and route["duration_min"] >= 1
        assert route["provider"] is not None
