"""Auth flow integration tests against real PostgreSQL (viram_test).

Requests run through the app's real session dependency (patched to the test DB
in conftest); isolation comes from function-scoped TRUNCATE.
"""

import uuid


def _email() -> str:
    return f"auth-{uuid.uuid4().hex[:10]}@example.com"


def test_register_login_me_roundtrip(client):
    email = _email()
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngPass!23", "display_name": "Test Traveller"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["email"] == email
    assert body["user"]["account_role"] == "USER"
    assert "access_token" in body["tokens"]
    assert "refresh_token" in body["tokens"]

    access = body["tokens"]["access_token"]
    me = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == email




def test_register_duplicate_email_conflict(client):
    email = _email()
    payload = {"email": email, "password": "Str0ngPass!23", "display_name": "A"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201


    # Second registration with the same email must hit the unique constraint
    # path and return the standard conflict envelope.
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 409, r.text


def test_login_wrong_password_401(client):
    email = _email()
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngPass!23", "display_name": "B"},
    )


    r = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-pass"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTHENTICATION_FAILED"


def test_refresh_rotation_and_logout(client):
    email = _email()
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngPass!23", "display_name": "C"},
    ).json()


    tokens = reg["tokens"]
    r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r1.status_code == 200, r1.text
    new_tokens = r1.json()

    # Old refresh token must be dead (rotation).
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r2.status_code == 401

    # Logout with the new token revokes it.
    r3 = client.post("/api/v1/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
    assert r3.status_code == 204
    r4 = client.post("/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    assert r4.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/users/me").status_code == 401
    assert (
        client.get("/api/v1/users/me", headers={"Authorization": "Bearer garbage"})
        .status_code
        == 401
    )


def test_profile_get_and_update(client):
    email = _email()
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngPass!23", "display_name": "D"},
    ).json()
    access = reg["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {access}"}


    prof = client.get("/api/v1/users/me/profile", headers=headers)
    assert prof.status_code == 200
    assert prof.json()["full_name"] == "D"

    upd = client.patch(
        "/api/v1/users/me/profile",
        headers=headers,
        json={"bio": "Heritage traveller", "phone": "9999999999"},
    )
    assert upd.status_code == 200
    assert upd.json()["bio"] == "Heritage traveller"


def test_preferences_upsert_and_validation(client):
    email = _email()
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngPass!23", "display_name": "E"},
    ).json()
    access = reg["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {access}"}


    r = client.patch(
        "/api/v1/users/me/preferences",
        headers=headers,
        json={"interests": ["heritage", "food"], "pace": "RELAXED", "budget_level": "MID"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["interests"] == ["heritage", "food"]

    bad = client.patch(
        "/api/v1/users/me/preferences", headers=headers, json={"pace": "SUPERFAST"}
    )
    assert bad.status_code == 422
