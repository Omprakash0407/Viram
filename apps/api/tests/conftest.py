"""Pytest configuration.

Strategy:
- One real test database (viram_test) per session: created, migrated via Alembic, dropped.
- VIRAM_DATABASE_URL is set before app import so the whole process (app + Alembic)
  targets the test database.
- Function-scoped TRUNCATE before each test gives full isolation with no shared state.
"""

import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEST_DB_URL = "postgresql+asyncpg://viram:viram@localhost:5432/viram_test"
ADMIN_URL = "postgresql+asyncpg://viram:viram@localhost:5432/postgres"

# Must be set before any app import: settings (and Alembic env.py) read it,
# so the whole test process - app + migrations - targets the test database.
os.environ["VIRAM_DATABASE_URL"] = TEST_DB_URL

_TABLES = (
    "payment_webhook_events, refunds, payments, "
    "guide_availability, guide_bookings, guide_profiles, hotel_bookings, "
    "room_types, hotels, admin_audit_log, itinerary_items, itinerary_days, "
    "itineraries, recommendation_items, recommendation_runs, trips, places, "
    "place_categories, cities, states, traveller_profiles, user_sessions, "
    "user_preferences, users"
)


async def _recreate_test_db() -> None:
    admin = create_async_engine(ADMIN_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text("DROP DATABASE IF EXISTS viram_test"))
        await conn.execute(text("CREATE DATABASE viram_test"))
    await admin.dispose()


async def _drop_test_db() -> None:
    admin = create_async_engine(ADMIN_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text("DROP DATABASE IF EXISTS viram_test"))
    await admin.dispose()


async def _truncate_all() -> None:
    eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    async with eng.begin() as conn:
        await conn.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))
    await eng.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_test_db():
    asyncio.run(_recreate_test_db())

    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(APP_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(APP_DIR, "migrations"))
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.upgrade(cfg, "head")

    # Point the app at the test database for the whole session.
    import app.core.database as dbmod

    test_engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    dbmod.engine = test_engine
    dbmod.AsyncSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

    yield

    asyncio.run(test_engine.dispose())
    asyncio.run(_drop_test_db())


@pytest.fixture(autouse=True)
def clean_db():
    asyncio.run(_truncate_all())
    yield


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
