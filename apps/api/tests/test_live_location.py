"""Phase 8b: live location sharing between trip companions.

Security matrix: only head/ACTIVE companions can share or read; outsiders and
non-members get 403; reads never include the viewer's own position; opt-out
hides the traveller instantly; removed companions lose access; coordinates are
validated; the maintenance purge clears expired retention windows.
"""

from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import select

from app.modules.planning import location_service


def _register(client, email, name):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": name},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    return data["user"]["id"], {
        "Authorization": f"Bearer {data['tokens']['access_token']}"
    }


async def _seed_city() -> str:
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
            await db.commit()
        return str(city.id)


def _make_trip(client, headers, city_id):
    r = client.post(
        "/api/v1/trips",
        headers=headers,
        json={
            "city_id": city_id,
            "starts_on": "2026-12-10",
            "ends_on": "2026-12-12",
            "party_size": 4,
            "moods": ["FOOD_CULTURE"],
            "budget_tier": "MODERATE",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _invite_and_accept(client, head_h, member_h, trip_id, member_email):
    r = client.post(
        f"/api/v1/trips/{trip_id}/companions",
        headers=head_h, json={"email": member_email},
    )
    assert r.status_code == 201, r.text
    inv = client.get("/api/v1/companions/invitations", headers=member_h).json()["items"]
    assert inv, "invitation should exist"
    r = client.post(f"/api/v1/companions/invitations/{inv[0]['id']}/accept", headers=member_h)
    assert r.status_code == 200, r.text


def test_location_requires_membership(client):
    """A signed-in non-member can neither share nor read a trip's locations."""
    city_id = asyncio.run(_seed_city())
    _, head_h = _register(client, "loc-head@test.io", "Head")
    trip_id = _make_trip(client, head_h, city_id)
    _, stranger_h = _register(client, "loc-stranger@test.io", "Stranger")

    r = client.put(
        f"/api/v1/trips/{trip_id}/location",
        headers=stranger_h,
        json={"latitude": 20.1, "longitude": 85.1},
    )
    assert r.status_code == 403, r.text
    r = client.get(f"/api/v1/trips/{trip_id}/location", headers=stranger_h)
    assert r.status_code == 403, r.text


def test_share_and_read_between_companions(client):
    """Head shares; an invited+accepted companion reads the head's position."""
    city_id = asyncio.run(_seed_city())
    head_id, head_h = _register(client, "loc-pair-head@test.io", "Head")
    _, member_h = _register(client, "loc-pair-member@test.io", "Member")
    trip_id = _make_trip(client, head_h, city_id)
    _invite_and_accept(client, head_h, member_h, trip_id, "loc-pair-member@test.io")

    # head shares a position
    r = client.put(
        f"/api/v1/trips/{trip_id}/location",
        headers=head_h,
        json={"latitude": 20.27, "longitude": 85.84, "accuracy_m": 12},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sharing"] is True

    # companion reads: sees the head, never themselves
    r = client.get(f"/api/v1/trips/{trip_id}/location", headers=member_h)
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [item["user_id"] for item in body["items"]]
    assert ids == [head_id], ids
    item = body["items"][0]
    assert abs(item["latitude"] - 20.27) < 1e-4
    assert item["display_name"] == "Head"

    # head's own read does not echo their position back
    r = client.get(f"/api/v1/trips/{trip_id}/location", headers=head_h)
    assert r.json()["items"] == []
    assert r.json()["sharing"] is True


def test_opt_out_hides_instantly(client):
    """Deleting the share row stops sharing; the reader sees an empty list."""
    city_id = asyncio.run(_seed_city())
    head_id, head_h = _register(client, "loc-out-head@test.io", "Head")
    _, member_h = _register(client, "loc-out-member@test.io", "Member")
    trip_id = _make_trip(client, head_h, city_id)
    _invite_and_accept(client, head_h, member_h, trip_id, "loc-out-member@test.io")

    client.put(f"/api/v1/trips/{trip_id}/location", headers=head_h,
               json={"latitude": 20.0, "longitude": 85.0})
    r = client.delete(f"/api/v1/trips/{trip_id}/location", headers=head_h)
    assert r.status_code == 200 and r.json()["sharing"] is False

    r = client.get(f"/api/v1/trips/{trip_id}/location", headers=member_h)
    assert r.json()["items"] == []


def test_removed_companion_loses_access(client):
    """A removed companion can no longer share or read."""
    city_id = asyncio.run(_seed_city())
    head_id, head_h = _register(client, "loc-rm-head@test.io", "Head")
    member_id, member_h = _register(client, "loc-rm-member@test.io", "Member")
    trip_id = _make_trip(client, head_h, city_id)
    _invite_and_accept(client, head_h, member_h, trip_id, "loc-rm-member@test.io")

    # member shares fine while active
    r = client.put(f"/api/v1/trips/{trip_id}/location", headers=member_h,
                   json={"latitude": 20.0, "longitude": 85.0})
    assert r.status_code == 200

    # head removes the member
    listing = client.get(f"/api/v1/trips/{trip_id}/companions", headers=head_h).json()["items"]
    row = next(c for c in listing if c["companion_user_id"] == member_id)
    r = client.delete(f"/api/v1/trips/{trip_id}/companions/{row['id']}", headers=head_h)
    assert r.status_code in (204, 200), r.text

    r = client.put(f"/api/v1/trips/{trip_id}/location", headers=member_h,
                   json={"latitude": 20.0, "longitude": 85.0})
    assert r.status_code == 403, r.text


def test_coordinate_validation(client):
    """Out-of-range coordinates are rejected by request validation."""
    city_id = asyncio.run(_seed_city())
    _, head_h = _register(client, "loc-val-head@test.io", "Head")
    trip_id = _make_trip(client, head_h, city_id)
    r = client.put(f"/api/v1/trips/{trip_id}/location", headers=head_h,
                   json={"latitude": 999.0, "longitude": 85.0})
    assert r.status_code == 422, r.text


def test_purge_expired(client):
    """The maintenance sweep deletes only rows past their purge date."""
    city_id = asyncio.run(_seed_city())
    _, head_h = _register(client, "loc-purge-head@test.io", "Head")
    trip_id = _make_trip(client, head_h, city_id)

    # real, reachable share row (real FKs), then age it past retention
    r = client.put(f"/api/v1/trips/{trip_id}/location", headers=head_h,
                   json={"latitude": 20.0, "longitude": 85.0})
    assert r.status_code == 200, r.text

    async def _age_row():
        from app.core.database import AsyncSessionLocal
        from app.models.planning import CompanionLocationShare

        async with AsyncSessionLocal() as db:
            row = (await db.scalars(select(CompanionLocationShare))).one()
            row.purge_date = date(2026, 1, 1)
            await db.commit()

    async def _purge():
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            return await location_service.purge_expired(db)

    async def _count():
        from app.core.database import AsyncSessionLocal
        from app.models.planning import CompanionLocationShare

        async with AsyncSessionLocal() as db:
            return len((await db.scalars(select(CompanionLocationShare))).all())

    asyncio.run(_age_row())
    removed = asyncio.run(_purge())
    assert removed >= 1
    assert asyncio.run(_count()) == 0
