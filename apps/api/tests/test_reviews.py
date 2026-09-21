"""Place review tests (design doc §24) — self-contained seed per test."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_DB_URL = "postgresql+asyncpg://viram:viram@localhost:5432/viram_test"


def _seed_review_rows() -> None:
    """One state/city/category/place for the review endpoints."""
    from app.models.geo import City, Place, PlaceCategory, State

    async def run() -> None:
        engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            state = State(name="Review S", slug="review-s")
            db.add(state)
            await db.flush()
            city = City(
                state_id=state.id, name="Review C", slug="review-c", latitude="20", longitude="85"
            )
            cat = PlaceCategory(name="ReviewCat", slug="reviewcat")
            db.add_all([city, cat])
            await db.flush()
            db.add(
                Place(
                    city_id=city.id,
                    category_id=cat.id,
                    name="Review Place",
                    slug="review-place",
                    description="A review test place.",
                    latitude="20",
                    longitude="85",
                    classification="POPULAR",
                )
            )
            await db.commit()
        await engine.dispose()

    asyncio.run(run())


def _register(client, email: str) -> dict:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "TestPass123!", "display_name": email.split("@")[0]},
    )
    assert r.status_code == 201, r.text
    return {"headers": {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}}


def test_review_crud_and_aggregates(client):
    _seed_review_rows()
    slug = "review-place"
    a = _register(client, "rev-a@t.com")
    b = _register(client, "rev-b@t.com")

    # create
    r = client.post(
        f"/api/v1/places/{slug}/reviews",
        headers=a["headers"],
        json={"rating": 5, "title": "Loved it", "body": "A genuinely memorable visit."},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["review"]["rating"] == 5
    assert data["review"]["author"]["display_name"].startswith("rev-a")
    assert data["rating_avg"] == 5.0 and data["review_count"] == 1
    review_id = data["review"]["id"]

    # public list includes it with aggregates
    r = client.get(f"/api/v1/places/{slug}/reviews")
    assert r.status_code == 200
    listing = r.json()
    assert any(item["id"] == review_id for item in listing["items"])
    assert listing["rating_avg"] == 5.0

    # second review moves the average
    r = client.post(
        f"/api/v1/places/{slug}/reviews",
        headers=b["headers"],
        json={"rating": 3, "body": "Good but crowded on weekends, honestly."},
    )
    assert r.status_code == 201
    assert r.json()["rating_avg"] == 4.0

    # duplicate author+place → 409
    r = client.post(
        f"/api/v1/places/{slug}/reviews",
        headers=a["headers"],
        json={"rating": 4, "body": "Trying to review twice should fail."},
    )
    assert r.status_code == 409

    # rating bounds and short body → 422
    for payload in (
        {"rating": 0, "body": "Rating below the range."},
        {"rating": 6, "body": "Rating above the range."},
        {"rating": 4, "body": "short"},
    ):
        r = client.post(f"/api/v1/places/{slug}/reviews", headers=b["headers"], json=payload)
        assert r.status_code == 422

    # other user cannot delete
    r = client.delete(f"/api/v1/places/reviews/{review_id}", headers=b["headers"])
    assert r.status_code == 403

    # owner deletes → aggregates recalc
    r = client.delete(f"/api/v1/places/reviews/{review_id}", headers=a["headers"])
    assert r.status_code == 204
    r = client.get(f"/api/v1/places/{slug}/reviews")
    listing = r.json()
    assert all(item["id"] != review_id for item in listing["items"])
    assert listing["rating_avg"] == 3.0 and listing["review_count"] == 1

    # unknown place → 404
    r = client.get("/api/v1/places/definitely-not-a-place/reviews")
    assert r.status_code == 404

    # unauthenticated create → 401
    r = client.post(
        f"/api/v1/places/{slug}/reviews",
        json={"rating": 3, "body": "Anonymous reviews must be rejected."},
    )
    assert r.status_code == 401
