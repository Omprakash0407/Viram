"""Phase 8a: avatars + travelling-together companions.

Covers the security matrix: only the head invites/removes; only the invitee
responds; companions get read-only trip access (mutations still 403); private
data (email) never leaks through companion shapes; avatar validation.
"""

import asyncio


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
    from sqlalchemy import select

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


# --- avatars ------------------------------------------------------------------


def test_avatar_roundtrip_and_validation(client):
    _, head = _register(client, "avatar1@test.io", "Avatar One")

    good = "data:image/png;base64," + "A" * 100
    r = client.patch(
        "/api/v1/users/me/profile",
        headers=head,
        json={"avatar_url": good},
    )
    assert r.status_code == 200, r.text
    assert r.json()["avatar_url"] == good

    # /users/me surfaces it too (header bubble needs this)
    r = client.get("/api/v1/users/me", headers=head)
    assert r.status_code == 200
    assert r.json()["avatar_url"] == good

    # clearing works
    r = client.patch(
        "/api/v1/users/me/profile", headers=head, json={"avatar_url": None}
    )
    assert r.status_code == 200
    assert r.json()["avatar_url"] is None

    # junk rejected
    r = client.patch(
        "/api/v1/users/me/profile",
        headers=head,
        json={"avatar_url": "javascript:alert(1)"},
    )
    assert r.status_code == 422

    # http (not https) rejected
    r = client.patch(
        "/api/v1/users/me/profile",
        headers=head,
        json={"avatar_url": "http://insecure.example/pic.png"},
    )
    assert r.status_code == 422

    # oversize data URL rejected
    r = client.patch(
        "/api/v1/users/me/profile",
        headers=head,
        json={"avatar_url": "data:image/png;base64," + "A" * 70_000},
    )
    assert r.status_code == 422


# --- companions: invite / respond -----------------------------------------------


def test_invite_requires_registered_account_and_head_role(client):
    _, head = _register(client, "head@test.io", "Trip Head")
    _, other = _register(client, "member@test.io", "Member")
    city_id = asyncio.run(_seed_city())
    trip_id = _make_trip(client, head, city_id)

    # stranger cannot invite to someone else's trip
    r = client.post(
        f"/api/v1/trips/{trip_id}/companions",
        headers=other,
        json={"email": "someone@else.io"},
    )
    assert r.status_code == 403

    # head cannot invite themselves
    r = client.post(
        f"/api/v1/trips/{trip_id}/companions",
        headers=head,
        json={"email": "head@test.io"},
    )
    assert r.status_code == 422

    # unregistered email is rejected without leaking account existence
    r = client.post(
        f"/api/v1/trips/{trip_id}/companions",
        headers=head,
        json={"email": "ghost@test.io"},
    )
    assert r.status_code == 422

    # invite the member — response must not leak the member's email
    r = client.post(
        f"/api/v1/trips/{trip_id}/companions",
        headers=head,
        json={"email": "member@test.io"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    row_id = body["id"]
    assert body["status"] == "INVITED"
    assert "email" not in body

    # duplicate active invite conflicts
    r = client.post(
        f"/api/v1/trips/{trip_id}/companions",
        headers=head,
        json={"email": "member@test.io"},
    )
    assert r.status_code == 409

    # member sees it in their invitations
    r = client.get("/api/v1/companions/invitations", headers=other)
    assert r.status_code == 200
    invites = r.json()["items"]
    assert any(i["id"] == row_id for i in invites)
    assert any(i["invited_by_name"] == "Trip Head" for i in invites)

    # only the invitee can accept — the head cannot accept on their behalf
    r = client.post(f"/api/v1/companions/invitations/{row_id}/accept", headers=head)
    assert r.status_code == 403

    r = client.post(f"/api/v1/companions/invitations/{row_id}/accept", headers=other)
    assert r.status_code == 200
    assert r.json()["status"] == "ACTIVE"

    # double-respond conflicts
    r = client.post(f"/api/v1/companions/invitations/{row_id}/accept", headers=other)
    assert r.status_code == 409


def test_decline_and_reinvite(client):
    _, head = _register(client, "dhead@test.io", "Decline Head")
    _, other = _register(client, "dmember@test.io", "Decline Member")
    city_id = asyncio.run(_seed_city())
    trip_id = _make_trip(client, head, city_id)

    r = client.post(
        f"/api/v1/trips/{trip_id}/companions",
        headers=head,
        json={"email": "dmember@test.io"},
    )
    row_id = r.json()["id"]
    r = client.post(f"/api/v1/companions/invitations/{row_id}/decline", headers=other)
    assert r.status_code == 200
    assert r.json()["status"] == "DECLINED"

    # re-invite after decline re-opens the same row
    r = client.post(
        f"/api/v1/trips/{trip_id}/companions",
        headers=head,
        json={"email": "dmember@test.io"},
    )
    assert r.status_code == 201
    assert r.json()["id"] == row_id
    assert r.json()["status"] == "INVITED"


# --- companion trip read access -------------------------------------------------


def test_companion_read_only_trip_access(client):
    _, head = _register(client, "rhead@test.io", "Read Head")
    _, member, = _register(client, "rmember@test.io", "Read Member")
    city_id = asyncio.run(_seed_city())
    trip_id = _make_trip(client, head, city_id)

    # before accepting: no access
    r = client.get(f"/api/v1/trips/{trip_id}", headers=member)
    assert r.status_code == 403

    r = client.post(
        f"/api/v1/trips/{trip_id}/companions",
        headers=head,
        json={"email": "rmember@test.io"},
    )
    row_id = r.json()["id"]
    client.post(f"/api/v1/companions/invitations/{row_id}/accept", headers=member)

    # accepted companion can READ the shared trip
    r = client.get(f"/api/v1/trips/{trip_id}", headers=member)
    assert r.status_code == 200
    body = r.json()
    assert body["viewer_role"] == "COMPANION"
    assert body["party_size"] == 4

    # ...but cannot mutate it (read-only grant)
    r = client.patch(f"/api/v1/trips/{trip_id}/extend", headers=member,
                     json={"days": 2})
    assert r.status_code == 403
    r = client.post(f"/api/v1/trips/{trip_id}/itinerary/items", headers=member,
                    json={"day_number": 1, "custom_title": "hijack"})
    assert r.status_code == 403
    r = client.post(f"/api/v1/trips/{trip_id}/recommendations", headers=member)
    assert r.status_code == 403

    # head sees themselves as HEAD
    r = client.get(f"/api/v1/trips/{trip_id}", headers=head)
    assert r.json()["viewer_role"] == "HEAD"

    # removing the companion revokes access
    r = client.delete(f"/api/v1/trips/{trip_id}/companions/{row_id}", headers=head)
    assert r.status_code == 204
    r = client.get(f"/api/v1/trips/{trip_id}", headers=member)
    assert r.status_code == 403


def test_companion_list_is_head_only(client):
    _, head = _register(client, "lhead@test.io", "List Head")
    _, member, = _register(client, "lmember@test.io", "List Member")
    city_id = asyncio.run(_seed_city())
    trip_id = _make_trip(client, head, city_id)

    r = client.post(
        f"/api/v1/trips/{trip_id}/companions",
        headers=head,
        json={"email": "lmember@test.io"},
    )
    row_id = r.json()["id"]
    client.post(f"/api/v1/companions/invitations/{row_id}/accept", headers=member)

    # member cannot enumerate the trip's companions
    r = client.get(f"/api/v1/trips/{trip_id}/companions", headers=member)
    assert r.status_code == 403

    r = client.get(f"/api/v1/trips/{trip_id}/companions", headers=head)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "ACTIVE"
    assert items[0]["name"] == "List Member"
    assert "email" not in items[0]
