"""Phase 7 tests: providers (§4, §5, §17), identity verification, admin queue."""

from __future__ import annotations

import uuid


def _register(client, email: str) -> dict:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "TestPass123!", "display_name": email.split("@")[0]},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _make_admin(client, email: str | None = None) -> dict:
    """Promote a fresh user to ADMIN directly in the test DB."""
    import asyncio

    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.models.user import User

    email = email or f"admin-{uuid.uuid4().hex[:8]}@t.com"
    _register(client, email)

    async def run() -> None:
        engine = create_async_engine(
            "postgresql+asyncpg://viram:viram@localhost:5432/viram_test", poolclass=NullPool
        )
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            await db.execute(update(User).where(User.email == email).values(account_role="ADMIN"))
            await db.commit()
        await engine.dispose()

    asyncio.run(run())
    return _login(client, email)


def _login(client, email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _city_id(client) -> str:
    """Seed (once per call) a test state+city via the app session, like test_commerce."""
    import asyncio

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.models.geo import City, State

    async def run() -> str:
        engine = create_async_engine(
            "postgresql+asyncpg://viram:viram@localhost:5432/viram_test", poolclass=NullPool
        )
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            city = await db.scalar(select(City).where(City.slug == "test-city"))
            if city is None:
                state = State(name="Test State", slug="test-state")
                db.add(state)
                await db.flush()
                city = City(state_id=state.id, name="Test City", slug="test-city",
                            latitude=20.0, longitude=85.0)
                db.add(city)
                await db.commit()
                await db.refresh(city)
            cid = str(city.id)
        await engine.dispose()
        return cid

    return asyncio.run(run())


def _verify_identity(client, auth: dict) -> str:
    r = client.post("/api/v1/identity/verify/init", headers=auth,
                    params={"id_proof_type": "AADHAAR"})
    assert r.status_code == 201, r.text
    vid = r.json()["verification"]["id"]
    r = client.post(f"/api/v1/identity/verify/{vid}/complete", headers=auth)
    assert r.status_code == 200, r.text
    return vid


# ---------- Business profiles ----------

def test_business_crud_and_visibility(client):
    auth = _register(client, f"biz-{uuid.uuid4().hex[:8]}@t.com")
    city_id = _city_id(client)

    # create → PENDING, PRIVATE
    r = client.post(
        "/api/v1/businesses", headers=auth,
        json={"name": "Raghurajpur Art Corner", "category": "ARTISAN", "city_id": city_id,
              "services": ["Pattachitra", "Palm leaf engraving"],
              "public_phone": "+91-90000-00000"},
    )
    assert r.status_code == 201, r.text
    biz = r.json()
    assert biz["status"] == "PENDING" and biz["visibility"] == "PRIVATE"
    bid = biz["id"]

    # not in the public wall while pending
    r = client.get("/api/v1/partners")
    assert r.status_code == 200
    assert all(i["id"] != bid for i in r.json()["items"])

    # owner lists own businesses
    r = client.get("/api/v1/businesses/mine", headers=auth)
    assert any(i["id"] == bid for i in r.json())

    # update keeps it pending for re-review
    r = client.patch(f"/api/v1/businesses/{bid}", headers=auth,
                     json={"description": "Family artisan studio since 1942."})
    assert r.status_code == 200 and r.json()["status"] == "PENDING"

    # invalid category rejected
    r = client.post("/api/v1/businesses", headers=auth,
                    json={"name": "X Corp", "category": "SPACESHIPS", "city_id": city_id})
    assert r.status_code == 422

    # another user cannot see or edit it (ownership, §2)
    other = _register(client, f"other-{uuid.uuid4().hex[:8]}@t.com")
    r = client.patch(f"/api/v1/businesses/{bid}", headers=other,
                     json={"description": "hijack"})
    assert r.status_code == 403


def test_partners_public_wall_filters(client):
    r = client.get("/api/v1/partners")
    assert r.status_code == 200
    items = r.json()["items"]
    # public shape exposes no owner/status/ADMIN_ONLY data (§24)
    assert all("user_id" not in i and "status" not in i and "review_note" not in i
               for i in items)
    r2 = client.get("/api/v1/partners", params={"category": "CAFE"})
    assert all(i["category"] == "CAFE" for i in r2.json()["items"])
    assert client.get("/api/v1/partners", params={"category": "NOPE"}).status_code == 422


# ---------- Guide profile ----------

def test_guide_upsert_flow(client):
    auth = _register(client, f"guide-{uuid.uuid4().hex[:8]}@t.com")
    city_id = _city_id(client)

    # no profile yet → 404
    r = client.get("/api/v1/guides/me", headers=auth)
    assert r.status_code == 404

    r = client.put(
        "/api/v1/guides/me", headers=auth,
        json={"public_name": "Rakesh Pathania", "languages": ["Odia", "Hindi", "English"],
              "expertise": ["Heritage walks"], "areas_served": ["Puri", "Konark"],
              "city_id": city_id, "day_rate_paise": 150000},
    )
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["status"] == "PENDING" and g["visibility"] == "PRIVATE"

    # idempotent second upsert updates the same row
    r2 = client.put(
        "/api/v1/guides/me", headers=auth,
        json={"public_name": "Rakesh P.", "languages": ["Odia"], "expertise": [],
              "areas_served": [], "city_id": city_id, "day_rate_paise": 160000},
    )
    assert r2.status_code == 200 and r2.json()["id"] == g["id"]
    assert r2.json()["day_rate_paise"] == 160000

    # unauthenticated access denied
    assert client.get("/api/v1/guides/me").status_code == 401


# ---------- Identity verification ----------

def test_identity_flow_and_privacy(client):
    auth = _register(client, f"ident-{uuid.uuid4().hex[:8]}@t.com")

    r = client.get("/api/v1/identity/verify/me", headers=auth)
    assert r.status_code == 200 and r.json()["identity_verified"] is False

    r = client.post("/api/v1/identity/verify/init", headers=auth,
                    params={"id_proof_type": "AADHAAR"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert "DEMO" in body["demo_note"].upper()  # honest labelling
    vid = body["verification"]["id"]
    assert body["verification"]["status"] == "PENDING"

    # no document-number field anywhere in the response
    assert "aadhaar_number" not in str(body).lower()

    r = client.post(f"/api/v1/identity/verify/{vid}/complete", headers=auth)
    assert r.status_code == 200, r.text
    done = r.json()["verification"]
    assert done["status"] == "APPROVED"
    assert done["verified_at"] is not None
    # the opaque provider reference stays internal — never in user shapes
    assert "provider_reference" not in done

    r = client.get("/api/v1/identity/verify/me", headers=auth)
    assert r.json()["identity_verified"] is True

    # completing a closed session is rejected
    assert client.post(f"/api/v1/identity/verify/{vid}/complete", headers=auth).status_code == 422

    # another user cannot complete someone else's session (IDOR check)
    other = _register(client, f"other-{uuid.uuid4().hex[:8]}@t.com")
    assert client.post(f"/api/v1/identity/verify/{vid}/complete", headers=other).status_code == 404

    # invalid proof type
    r = client.post("/api/v1/identity/verify/init", headers=auth,
                    params={"id_proof_type": "LIBRARY_CARD"})
    assert r.status_code == 422


# ---------- Admin verification queue ----------

def test_admin_queue_approve_flow(client):
    auth = _register(client, f"owner-{uuid.uuid4().hex[:8]}@t.com")
    admin_auth = _make_admin(client)
    city_id = _city_id(client)

    _verify_identity(client, auth)

    r = client.post("/api/v1/businesses", headers=auth,
                    json={"name": "Chilika Boat Homestay", "category": "HOMESTAY",
                          "city_id": city_id})
    bid = r.json()["id"]

    r = client.put("/api/v1/guides/me", headers=auth,
                   json={"public_name": "Chilika Guide", "languages": ["Odia"],
                         "expertise": [], "areas_served": [], "city_id": city_id,
                         "day_rate_paise": 120000})
    gid = r.json()["id"]

    # queue shows both with the owner's identity flag
    r = client.get("/api/v1/admin/providers", headers=admin_auth,
                   params={"status": "PENDING"})
    assert r.status_code == 200, r.text
    mine = [x for x in r.json() if x["id"] in (bid, gid)]
    assert len(mine) == 2
    assert all(x["owner_identity_verified"] for x in mine)
    assert all("owner_email" in x for x in mine)

    # non-admin blocked
    assert client.get("/api/v1/admin/providers", headers=auth).status_code == 403

    # approve the business → PUBLIC + visible in the wall
    r = client.post(f"/api/v1/admin/providers/BUSINESS/{bid}/review",
                    headers=admin_auth,
                    json={"decision": "APPROVED", "admin_note": "Photos verified on call."})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED" and r.json()["visibility"] == "PUBLIC"

    r = client.get("/api/v1/partners", params={"category": "HOMESTAY"})
    assert any(i["id"] == bid for i in r.json()["items"])

    # suspend → hidden from the wall, still in the queue
    r = client.post(f"/api/v1/admin/providers/BUSINESS/{bid}/review",
                    headers=admin_auth,
                    json={"decision": "SUSPENDED", "admin_note": "Complaint received."})
    assert r.status_code == 200
    r = client.get("/api/v1/partners", params={"category": "HOMESTAY"})
    assert all(i["id"] != bid for i in r.json()["items"])

    # guide approve → public discovery (commerce's authenticated browse, §5)
    r = client.post(f"/api/v1/admin/providers/GUIDE/{gid}/review",
                    headers=admin_auth, json={"decision": "APPROVED"})
    assert r.status_code == 200
    r = client.get("/api/v1/guides", headers=admin_auth)
    assert any(g["id"] == gid for g in r.json()["items"])

    # invalid decision rejected
    r = client.post(f"/api/v1/admin/providers/GUIDE/{gid}/review",
                    headers=admin_auth, json={"decision": "MAYBE"})
    assert r.status_code == 422

    # every decision audited
    r = client.get("/api/v1/admin/audit-log", headers=admin_auth)
    actions = [i["action"] for i in r.json()["items"]]
    assert "APPROVE_BUSINESS" in actions and "SUSPEND_BUSINESS" in actions
    assert "APPROVE_GUIDE" in actions


def test_suggestion_source_in_app(client):
    """The in-app intake stamps source=IN_APP (§22)."""
    r = client.post(
        "/api/v1/community/suggestions",
        json={"submitter_name": "Local Kaka", "kind": "FOOD",
              "title": "Chhena poda of Nayagarh",
              "body": "A baked cheese dessert from Nayagarh district, traditionally made during festivals and offered at temples."},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "PENDING"

    import asyncio

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.models.intelligence import CommunitySuggestion

    async def run():
        engine = create_async_engine(
            "postgresql+asyncpg://viram:viram@localhost:5432/viram_test", poolclass=NullPool
        )
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            row = (
                await db.scalars(
                    select(CommunitySuggestion)
                    .order_by(CommunitySuggestion.created_at.desc()).limit(1)
                )
            ).first()
            assert row is not None and row.source == "IN_APP"
        await engine.dispose()

    asyncio.run(run())
