"""Planning flow tests (mock steps 1–6): geo reads, recommendations,
itinerary generation, customization, ownership isolation."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _register(client: TestClient, email: str) -> dict:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngPass!23", "display_name": "Plan Test"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    return {
        "headers": {"Authorization": f"Bearer {data['tokens']['access_token']}"},
        "user_id": data["user"]["id"],
    }


def _seed_minimal(client: TestClient) -> dict:
    """Insert one state/city/category/places directly via a service-level seed
    (tests use the same idempotent seed module against the test DB)."""
    import asyncio

    from app.core.database import AsyncSessionLocal
    from scripts.seed_odisha import seed

    async def run() -> dict:
        async with AsyncSessionLocal() as db:
            return await seed(db)

    counts = asyncio.run(run())
    assert counts["places"] >= 20

    r = client.get("/api/v1/geo/cities")
    assert r.status_code == 200
    cities = r.json()["items"]
    bbsr = next(c for c in cities if c["name"] == "Bhubaneswar")
    return {"city": bbsr}


def test_geo_endpoints(client: TestClient):
    _seed_minimal(client)
    states = client.get("/api/v1/geo/states").json()["items"]
    assert states[0]["name"] == "Odisha"
    places = client.get("/api/v1/geo/places?classification=LESSER_KNOWN").json()["items"]
    assert len(places) >= 10
    assert all(p["lesser_known_note"] for p in places)


def test_full_trip_flow(client: TestClient):
    _seed_minimal(client)
    ctx = _register(client, "plan-flow@test.com")
    headers = ctx["headers"]

    cities = client.get("/api/v1/geo/cities").json()["items"]
    city_id = next(c for c in cities if c["name"] == "Bhubaneswar")["id"]

    # step 1–4: create trip with duration, city, mood, budget
    r = client.post(
        "/api/v1/trips",
        headers=headers,
        json={
            "city_id": city_id,
            "starts_on": "2026-11-10",
            "ends_on": "2026-11-13",  # 4 days
            "party_size": 2,
            "moods": ["FOOD_CULTURE", "NATURE_RELAXATION"],
            "budget_tier": "MODERATE",
        },
    )
    assert r.status_code == 201, r.text
    trip = r.json()
    assert trip["status"] == "PLANNING"
    assert trip["preferences"]["days"] == 4
    trip_id = trip["id"]

    # step 5: recommendations (persisted so they can be accepted)
    r = client.post(
        f"/api/v1/trips/{trip_id}/recommendations?persist=true", headers=headers
    )
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["persisted"] is True
    assert len(rec["items"]) >= 3
    assert any(i["classification"] == "LESSER_KNOWN" for i in rec["items"]), (
        "plan must include hidden gems"
    )
    run_id = rec["run_id"]

    # accept the top 3, generate itinerary (step 6)
    top_ids = [i["id"] for i in rec["items"][:3]]
    r = client.post(
        f"/api/v1/trips/{trip_id}/recommendations/accept",
        headers=headers,
        json={"run_id": run_id, "item_ids": top_ids},
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"/api/v1/trips/{trip_id}/itinerary", headers=headers, json={"run_id": run_id}
    )
    assert r.status_code == 201, r.text
    itin = r.json()["itinerary"]
    assert len(itin["days"]) == 4  # date-derived day count
    placed = [it for it in itin["days"] if it["items"]]
    assert placed, "accepted places must land in the itinerary"

    # detail endpoint matches
    r = client.get(f"/api/v1/trips/{trip_id}", headers=headers)
    assert r.status_code == 200
    detail = r.json()
    assert detail["city"]["name"] == "Bhubaneswar"
    assert detail["itinerary"]["id"] == itin["id"]

    # duplicate itinerary rejected
    r = client.post(
        f"/api/v1/trips/{trip_id}/itinerary", headers=headers, json={"run_id": run_id}
    )
    assert r.status_code == 409

    # customize: add + remove
    r = client.post(
        f"/api/v1/trips/{trip_id}/itinerary/items",
        headers=headers,
        json={"day_number": 2, "custom_title": "Sunset at Khandagiri", "note": "bring water"},
    )
    assert r.status_code == 201, r.text
    item_id = r.json()["id"]
    r = client.delete(f"/api/v1/trips/{trip_id}/itinerary/items/{item_id}", headers=headers)
    assert r.status_code == 204


def test_trip_ownership_enforced(client: TestClient):
    _seed_minimal(client)
    owner = _register(client, "owner@test.com")
    other = _register(client, "other@test.com")
    city_id = next(
        c for c in client.get("/api/v1/geo/cities").json()["items"] if c["name"] == "Puri"
    )["id"]

    r = client.post(
        "/api/v1/trips",
        headers=owner["headers"],
        json={
            "city_id": city_id,
            "starts_on": "2026-12-01",
            "ends_on": "2026-12-02",
            "party_size": 1,
            "moods": ["NATURE_RELAXATION"],
            "budget_tier": "BUDGET",
        },
    )
    trip_id = r.json()["id"]

    # stranger cannot read, recommend, or delete items on someone else's trip
    assert client.get(f"/api/v1/trips/{trip_id}", headers=other["headers"]).status_code == 403
    assert (
        client.post(
            f"/api/v1/trips/{trip_id}/recommendations", headers=other["headers"]
        ).status_code
        == 403
    )
    bogus = uuid.uuid4()
    assert (
        client.delete(
            f"/api/v1/trips/{trip_id}/itinerary/items/{bogus}", headers=other["headers"]
        ).status_code
        == 403
    )


def test_trip_validation_errors(client: TestClient):
    _seed_minimal(client)
    ctx = _register(client, "validation@test.com")
    headers = ctx["headers"]
    city_id = client.get("/api/v1/geo/cities").json()["items"][0]["id"]

    # inverted dates
    r = client.post(
        "/api/v1/trips",
        headers=headers,
        json={
            "city_id": city_id,
            "starts_on": "2026-10-10",
            "ends_on": "2026-10-01",
            "moods": ["NATURE_RELAXATION"],
            "budget_tier": "BUDGET",
        },
    )
    assert r.status_code == 422

    # unknown mood / budget tier
    r = client.post(
        "/api/v1/trips",
        headers=headers,
        json={
            "city_id": city_id,
            "starts_on": "2026-10-10",
            "ends_on": "2026-10-12",
            "moods": ["NIGHTLIFE"],
            "budget_tier": "BUDGET",
        },
    )
    assert r.status_code == 422

    # unknown city → 404 envelope
    r = client.post(
        "/api/v1/trips",
        headers=headers,
        json={
            "city_id": str(uuid.uuid4()),
            "starts_on": "2026-10-10",
            "ends_on": "2026-10-12",
            "moods": ["NATURE_RELAXATION"],
            "budget_tier": "BUDGET",
        },
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_planning_meta_endpoints(client: TestClient):
    moods = client.get("/api/v1/planning/moods").json()["items"]
    assert {m["key"] for m in moods} == {
        "NATURE_RELAXATION",
        "CITY_LIFE",
        "ADVENTURE_THRILL",
        "FOOD_CULTURE",
    }
    tiers = client.get("/api/v1/planning/budget-tiers").json()["items"]
    assert len(tiers) == 4
    assert len(client.get("/api/v1/planning/reminders").json()["items"]) == 4
    assert len(client.get("/api/v1/planning/essentials").json()["items"]) == 6
    assert len(client.get("/api/v1/planning/precautions").json()["items"]) == 5
