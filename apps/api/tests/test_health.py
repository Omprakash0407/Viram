"""Health endpoint contract tests (no DB required)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_envelope() -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "environment" in body
    assert "version" in body


def test_health_has_no_secret_fields() -> None:
    resp = client.get("/api/v1/health")
    text = resp.text.lower()
    for forbidden in ("secret", "password", "razorpay", "database_url"):
        assert forbidden not in text, f"leaked field: {forbidden}"
