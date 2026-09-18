"""Seed Odisha demo data: 1 state, 5 cities, 8 categories, ~20 places.

Idempotent: existing slugs are skipped, safe to re-run. This is DEMO/EDITORIAL
data (design doc D12: seed data is data, the schema stays location-agnostic).
Ratings/popularity are editorial placeholder values for the MVP demo, not live
review aggregates.

Run:  ./.venv/Scripts/python.exe -m scripts.seed_odisha
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal as SessionLocal
from app.models.geo import City, Place, PlaceCategory, State

STATE = {"name": "Odisha", "slug": "odisha"}

CITIES = [
    {"name": "Bhubaneswar", "slug": "bhubaneswar", "lat": "20.2961", "lng": "85.8245"},
    {"name": "Puri", "slug": "puri", "lat": "19.8135", "lng": "85.8312"},
    {"name": "Konark", "slug": "konark", "lat": "19.8876", "lng": "86.0945"},
    {"name": "Chilika (Satapada)", "slug": "chilika-satapada", "lat": "19.6800", "lng": "85.4300"},
    {"name": "Daringbadi", "slug": "daringbadi", "lat": "19.9200", "lng": "84.1000"},
]

CATEGORIES = [
    {"name": "Heritage", "slug": "heritage"},
    {"name": "Nature", "slug": "nature"},
    {"name": "Wildlife", "slug": "wildlife"},
    {"name": "Scenic", "slug": "scenic"},
    {"name": "Adventure", "slug": "adventure"},
    {"name": "Culture", "slug": "culture"},
    {"name": "Food", "slug": "food"},
    {"name": "Lakes", "slug": "lakes"},
    {"name": "Fun", "slug": "fun"},
]

# (city_slug, category_slug, name, lat, lng, classification, note_or_None,
#  popularity, rating, visit_minutes)
PLACES = [
    ("bhubaneswar", "heritage", "Lingaraj Temple", "20.2382", "85.8340", "POPULAR", None, "95", "4.7", 90),
    ("bhubaneswar", "heritage", "Udayagiri & Khandagiri Caves", "20.2616", "85.7825", "POPULAR", None, "78", "4.4", 120),
    ("bhubaneswar", "culture", "Ekamra Heritage Walk (Old Town)", "20.2400", "85.8330", "LESSER_KNOWN", "Guided morning walk through 7th-century temples and living traditions.", "42", "4.6", 150),
    ("bhubaneswar", "food", "Unit-1 Market Food Street", "20.2700", "85.8400", "LESSER_KNOWN", "Local favourite for dahi bara aloo dum and chhena poda.", "35", "4.3", 60),
    ("bhubaneswar", "nature", "Ekamra Kanan Botanical Gardens", "20.2980", "85.8060", "POPULAR", None, "55", "4.2", 90),
    ("puri", "heritage", "Jagannath Temple (exterior view)", "19.8050", "85.8190", "POPULAR", None, "98", "4.8", 60),
    ("puri", "scenic", "Puri Beach (Swargadwar stretch)", "19.7990", "85.8130", "POPULAR", None, "88", "4.4", 120),
    ("puri", "culture", "Raghurajpur Heritage Village", "20.1700", "85.8700", "LESSER_KNOWN", "12 km from Puri: every house has at least one living Pattachitra artist. Palm-leaf engravings, tussar painting, wood carving; villagers demonstrate their craft and sell directly.", "48", "4.6", 120),
    ("puri", "food", "Abadha Mahaprasad Experience", "19.8055", "85.8180", "LESSER_KNOWN", "Traditional temple food culture explained by local guides.", "30", "4.5", 45),
    ("konark", "heritage", "Konark Sun Temple", "19.8876", "86.0945", "POPULAR", None, "96", "4.8", 150),
    ("konark", "scenic", "Chandrabhaga Beach", "19.8930", "86.1080", "POPULAR", None, "70", "4.3", 90),
    ("konark", "culture", "Kuruma Buddhist Site", "19.9100", "86.0700", "LESSER_KNOWN", "Excavated 9th-century Buddhist monastery most tourists miss.", "25", "4.2", 45),
    ("chilika-satapada", "lakes", "Chilika Lake Satapada (dolphin & bird watching)", "19.6800", "85.4300", "POPULAR", None, "85", "4.5", 240),
    ("chilika-satapada", "wildlife", "Nalabana Bird Sanctuary", "19.9700", "85.5300", "LESSER_KNOWN", "Migratory bird island, best Nov-Feb; reached by boat from Balugaon.", "40", "4.7", 240),
    ("chilika-satapada", "food", "Chilika Crab & Prawn Shacks", "19.6900", "85.4400", "LESSER_KNOWN", "Fisher-family-run shacks serving fresh lagoon catch.", "33", "4.4", 60),
    ("daringbadi", "scenic", "Doluri River & Coffee Gardens", "19.9350", "84.0850", "LESSER_KNOWN", "Kashmir-of-Odisha pine valleys and small coffee plantations.", "38", "4.3", 120),
    ("daringbadi", "nature", "Hill View Park Daringbadi", "19.9150", "84.0950", "POPULAR", None, "60", "4.2", 60),
    ("daringbadi", "adventure", "Badangia Waterfall Trek", "19.9500", "84.0700", "LESSER_KNOWN", "Short forest trek to a three-tier fall; local guide recommended.", "28", "4.4", 150),
    ("daringbadi", "wildlife", "Belghar Sanctuary (Kutia Kondh region)", "19.9800", "84.0300", "LESSER_KNOWN", "Elephant corridor grasslands with tribal village visits.", "30", "4.5", 240),
    ("bhubaneswar", "adventure", "Deras Dam", "20.1800", "85.7700", "LESSER_KNOWN", "Quiet reservoir 20 km from the city; kayaking in season.", "32", "4.1", 90),
    # --- user-contributed editorial data (2026-09-17) ---
    ("bhubaneswar", "nature", "Jhumka Eco Park", "20.2600", "85.7500", "POPULAR", None, "58", "4.2", 90),
    ("bhubaneswar", "nature", "Paikaraypur Hills", "20.2100", "85.7900", "LESSER_KNOWN", "Quiet hillock trails on the city outskirts, little-known even to locals.", "22", "4.1", 120),
    ("bhubaneswar", "nature", "Anandabana", "20.2900", "85.8000", "POPULAR", None, "62", "4.3", 90),
    ("bhubaneswar", "lakes", "Ansupa Nature Camp", "20.5400", "85.6200", "LESSER_KNOWN", "At Odisha's largest sweetwater lake; boating, bamboo sheds and migratory birds in winter.", "36", "4.4", 180),
    ("bhubaneswar", "fun", "Butterfly Trampoline Park", "20.3000", "85.8200", "POPULAR", None, "50", "4.1", 120),
    ("bhubaneswar", "fun", "MAAYA WORLD Illusion Theme Park", "20.2700", "85.8400", "POPULAR", None, "52", "4.2", 150),
    ("bhubaneswar", "fun", "The BOMBAI", "20.2900", "85.8300", "POPULAR", None, "48", "4.0", 120),
    ("puri", "lakes", "Chilika Lake (Satapada side)", "19.6800", "85.4300", "POPULAR", "Quietest tourist side of Asia's largest brackish-water lagoon, 50 km from Puri: dolphin watching, bird watching, boating through backwaters and small islands. Far quieter than the commercialised Barkul side.", "82", "4.5", 240),
    ("puri", "scenic", "Baliharachandi Beach", "19.6200", "85.6800", "LESSER_KNOWN", "Unspoiled beach 27 km from Puri where river meets ocean; picnic and sunset spot with the Baliharachandi Temple on a sand dune above.", "26", "4.4", 150),
]


async def seed(db: AsyncSession) -> dict:
    counts = {"states": 0, "cities": 0, "categories": 0, "places": 0}

    state = await db.scalar(select(State).where(State.slug == STATE["slug"]))
    if state is None:
        state = State(**STATE)
        db.add(state)
        await db.flush()
        counts["states"] += 1

    city_by_slug: dict[str, City] = {}
    for c in CITIES:
        city = await db.scalar(
            select(City).where(City.state_id == state.id, City.slug == c["slug"])
        )
        if city is None:
            city = City(
                state_id=state.id, name=c["name"], slug=c["slug"],
                latitude=Decimal(c["lat"]), longitude=Decimal(c["lng"]),
            )
            db.add(city)
            await db.flush()
            counts["cities"] += 1
        city_by_slug[c["slug"]] = city

    cat_by_slug: dict[str, PlaceCategory] = {}
    for cat in CATEGORIES:
        row = await db.scalar(select(PlaceCategory).where(PlaceCategory.slug == cat["slug"]))
        if row is None:
            row = PlaceCategory(name=cat["name"], slug=cat["slug"])
            db.add(row)
            await db.flush()
            counts["categories"] += 1
        cat_by_slug[cat["slug"]] = row

    for (city_slug, cat_slug, name, lat, lng, classification, note, pop, rating, minutes) in PLACES:
        slug = name.lower().replace("&", "and")
        import re

        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
        exists = await db.scalar(
            select(Place).where(Place.city_id == city_by_slug[city_slug].id, Place.slug == slug)
        )
        if exists is not None:
            # editorial upsert: refresh copy/scores, never duplicate rows
            exists.description = (
                f"{name} — demo editorial description for the VIRĀM MVP."
            )
            exists.lesser_known_note = note
            exists.popularity_score = Decimal(pop)
            exists.rating_avg = Decimal(rating)
            exists.typical_visit_minutes = int(minutes)
            continue
        db.add(
            Place(
                city_id=city_by_slug[city_slug].id,
                category_id=cat_by_slug[cat_slug].id,
                name=name,
                slug=slug,
                description=f"{name} — demo editorial description for the VIRĀM MVP.",
                latitude=Decimal(lat),
                longitude=Decimal(lng),
                classification=classification,
                lesser_known_note=note,
                popularity_score=Decimal(pop),
                rating_avg=Decimal(rating),
                review_count=0,
                typical_visit_minutes=int(minutes),
                status="ACTIVE",
            )
        )
        counts["places"] += 1

    await db.commit()
    return counts


async def main() -> None:
    async with SessionLocal() as db:
        counts = await seed(db)
        print(f"seeded: {counts}")


if __name__ == "__main__":
    asyncio.run(main())
