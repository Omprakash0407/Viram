"""Tests for GET /geo/places/{slug} (explore detail pages)."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_DB_URL = "postgresql+asyncpg://viram:viram@localhost:5432/viram_test"


def _seed_detail_rows() -> None:
    """Insert two places (one with a details payload) into the test DB."""
    from app.models.geo import City, Place, PlaceCategory, State

    async def run() -> None:
        engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            state = State(name="Detail S", slug="detail-s")
            db.add(state)
            await db.flush()  # populate state.id (server-side uuid default)
            city = City(
                state_id=state.id, name="Detail C", slug="detail-c", latitude="20", longitude="85"
            )
            cat = PlaceCategory(name="DetailCat", slug="detailcat")
            db.add_all([city, cat])
            await db.flush()
            main = Place(
                city_id=city.id,
                category_id=cat.id,
                name="Detail Main",
                slug="detail-main",
                description="A detail-page test place.",
                latitude="20",
                longitude="85",
                classification="POPULAR",
                details={
                    "tagline": "T",
                    "nearby": [
                        {"slug": "detail-near", "label": "~ 1 km"},
                        {"slug": "ghost-place", "label": "dropped"},
                    ],
                },
            )
            near = Place(
                city_id=city.id,
                category_id=cat.id,
                name="Detail Near",
                slug="detail-near",
                description="Neighbour.",
                latitude="20.1",
                longitude="85.1",
                classification="POPULAR",
            )
            db.add_all([main, near])
            await db.commit()
        await engine.dispose()

    asyncio.run(run())


def test_place_detail_404_for_unknown_slug(client):
    res = client.get("/api/v1/geo/places/no-such-place")
    assert res.status_code == 404


def test_place_detail_returns_editorial_payload_and_filters_nearby(client):
    _seed_detail_rows()
    res = client.get("/api/v1/geo/places/detail-main")
    assert res.status_code == 200
    body = res.json()
    assert body["slug"] == "detail-main"
    assert body["city"]["name"] == "Detail C"
    assert body["state"]["slug"] == "detail-s"
    assert body["details"]["tagline"] == "T"
    # ghost slug must be dropped; only the live neighbour remains
    assert [n["slug"] for n in body["details"]["nearby"]] == ["detail-near"]
    assert body["details"]["nearby"][0]["name"] == "Detail Near"
