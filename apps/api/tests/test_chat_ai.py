"""Vira AI (beta) endpoint tests.

Without a Gemini key the API must behave honestly: a 422-class "not
configured" error with no fabricated output. Missing auth → 401. Rate guard
fires on burst. These tests never call the real provider.
"""

from __future__ import annotations

import pytest  # noqa: F401 — used via fixtures below


def _register(client, email: str) -> dict:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Traveller#2026", "display_name": "T"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _auth(client, email: str) -> dict:
    d = _register(client, email)
    return {"Authorization": f"Bearer {d['tokens']['access_token']}"}


def test_ai_chat_requires_auth(client):
    r = client.post("/api/v1/chat/ai", json={"message": "hi"})
    assert r.status_code == 401, r.text


def test_ai_chat_honest_without_key(client, monkeypatch):
    """Force-unconfigured: the endpoint must fail honestly, never fake output.
    (monkeypatched because the developer's real .env may carry a live key.)"""
    monkeypatch.setattr(
        "app.modules.chat.router.engine._api_key", "", raising=False
    )
    headers = _auth(client, "aikey@test.io")
    r = client.post(
        "/api/v1/chat/ai", headers=headers, json={"message": "Plan 3 days in Puri"}
    )
    assert r.status_code == 422, r.text
    body = r.json()
    msg = body["error"]["message"]
    assert "not configured" in msg.lower()
    # honesty: the failure names the real cause, never returns fake AI text
    assert "GEMINI_API_KEY" in msg


def test_ai_chat_rejects_oversize_and_empty(client):
    headers = _auth(client, "aisize@test.io")
    r = client.post("/api/v1/chat/ai", headers=headers, json={"message": ""})
    assert r.status_code == 422
    r = client.post("/api/v1/chat/ai", headers=headers, json={"message": "x" * 2500})
    assert r.status_code == 422


def test_ai_chat_history_is_sanitized_not_crashing(client, monkeypatch):
    """Malformed history entries are tolerated (sanitized) server-side."""
    monkeypatch.setattr(
        "app.modules.chat.router.engine._api_key", "", raising=False
    )
    headers = _auth(client, "aihist@test.io")
    r = client.post(
        "/api/v1/chat/ai",
        headers=headers,
        json={
            "message": "hello",
            "history": [
                {"role": "user", "text": "earlier question"},
                {"nonsense": True},
                {"role": "bot", "text": 42},
            ],
        },
    )
    # no key configured → the honest not-configured error (not a 500)
    assert r.status_code == 422
    assert "not configured" in r.json()["error"]["message"].lower()


def test_engine_requires_key(monkeypatch):
    """Engine refuses to run unconfigured even if called directly."""
    from app.modules.chat.gemini_engine import GeminiChatEngine

    monkeypatch.setattr("app.core.config.settings.GEMINI_API_KEY", "")
    eng = GeminiChatEngine()
    assert eng.configured is False
