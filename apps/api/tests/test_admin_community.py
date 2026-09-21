"""Community suggestion + admin moderation tests (§14, §31, §32)."""

from __future__ import annotations


def _register(client, email: str) -> dict:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "TestPass123!", "display_name": email.split("@")[0]},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _make_admin(client) -> dict:
    """Promote a fresh user to ADMIN directly in the test DB."""
    import asyncio

    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.models.user import User

    headers = _register(client, "admin@t.com")
    email = "admin@t.com"

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
    return headers


def test_suggestion_flow(client):
    # public submission lands PENDING
    r = client.post(
        "/api/v1/community/suggestions",
        json={
            "submitter_name": "Ramesh P.",
            "contact": "ramesh@example.com",
            "kind": "FOOD",
            "title": "Chhena poda of Nimapada",
            "body": "The dahi chhena poda sold near Nimapada market is a protected local recipe.",
        },
    )
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["status"] == "PENDING"
    suggestion_id = s["id"]

    # invalid kind → 422 (via explicit validation error)
    r = client.post(
        "/api/v1/community/suggestions",
        json={
            "submitter_name": "X Y",
            "kind": "NOT_A_KIND",
            "title": "Invalid kind here",
            "body": "This submission uses an unsupported kind value.",
        },
    )
    assert r.status_code in (400, 422)

    # short body → 422
    r = client.post(
        "/api/v1/community/suggestions",
        json={"submitter_name": "X Y", "kind": "FOOD", "title": "Too short", "body": "tiny"},
    )
    assert r.status_code == 422

    # listing requires admin
    user_headers = _register(client, "nonadmin@t.com")
    r = client.get("/api/v1/admin/suggestions", headers=user_headers)
    assert r.status_code == 403

    # admin sees it in the queue
    admin_headers = _make_admin(client)
    r = client.get("/api/v1/admin/suggestions?status=PENDING", headers=admin_headers)
    assert r.status_code == 200
    assert any(item["id"] == suggestion_id for item in r.json()["items"])

    # reject with note
    r = client.post(
        f"/api/v1/admin/suggestions/{suggestion_id}/review",
        headers=admin_headers,
        json={"decision": "REJECTED", "admin_note": "Duplicate of an existing entry."},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"

    # second review of the same item → rejected (already reviewed)
    r = client.post(
        f"/api/v1/admin/suggestions/{suggestion_id}/review",
        headers=admin_headers,
        json={"decision": "APPROVED"},
    )
    assert r.status_code in (400, 409, 422)

    # invalid decision → 422
    r = client.post(
        f"/api/v1/admin/suggestions/{suggestion_id}/review",
        headers=admin_headers,
        json={"decision": "MAYBE"},
    )
    assert r.status_code in (400, 422)

    # audit trail recorded the decision (admin-only)
    r = client.get("/api/v1/admin/audit-log", headers=admin_headers)
    assert r.status_code == 200
    assert any(e["action"] == "REJECT_SUGGESTION" for e in r.json()["items"])

    # audit log blocked for non-admins
    r = client.get("/api/v1/admin/audit-log", headers=user_headers)
    assert r.status_code == 403
