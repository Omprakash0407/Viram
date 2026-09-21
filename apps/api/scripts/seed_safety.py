"""Seed safety data: national emergency numbers + Odisha facilities (design §29).

Emergency information is factual reference data, maintained separately from
traveller-generated content (design rule). Idempotent: re-running updates
phones/coords rather than duplicating.

Run:  ./.venv/Scripts/python.exe -m scripts.seed_safety
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.geo import City
from app.models.intelligence import EmergencyContact, EmergencyFacility

NATIONAL_CONTACTS = [
    ("Emergency (All-in-One)", "112", "National emergency number — police, fire, medical"),
    ("Police", "100", None),
    ("Fire", "101", None),
    ("Ambulance", "108", None),
    ("Women Helpline", "1091", None),
    ("Child Helpline", "1098", None),
    ("Tourist Helpline", "1363", "Ministry of Tourism multi-language helpline"),
]

FACILITIES_BY_CITY = {
    "bhubaneswar": [
        ("AIIMS Bhubaneswar", "HOSPITAL", "Sijua, Patrapada", "0674-248-2000", True, 20.2888, 85.7699),
        ("Capital Hospital", "HOSPITAL", "Unit-2, Ashok Nagar", "0674-253-4466", True, 20.2622, 85.8431),
        ("Kalinga Hospital", "HOSPITAL", "Nandankanan Road", "0674-238-1111", True, 20.2967, 85.8159),
    ],
    "puri": [
        ("District Headquarters Hospital Puri", "HOSPITAL", "Hospital Road", "06752-223-333", True, 19.8107, 85.8309),
        ("Puri Sea Beach Police Post", "POLICE", "Swargadwar", "100", False, 19.8050, 85.8260),
    ],
    "konark": [
        ("Konark Community Health Centre", "HOSPITAL", "Konark Town", "06758-236-222", False, 19.8876, 86.0945),
    ],
    "chilika-satapada": [
        ("Satapada Primary Health Centre", "CLINIC", "Satapada", "06752-256-234", False, 19.6850, 85.4360),
    ],
    "daringbadi": [
        ("Daringbadi Community Health Centre", "HOSPITAL", "Daringbadi Town", "06816-255-333", False, 20.0458, 84.1000),
    ],
}


async def seed(db: AsyncSession) -> None:
    # National contacts (idempotent on label)
    for label, phone, desc in NATIONAL_CONTACTS:
        existing = await db.scalar(
            select(EmergencyContact).where(
                EmergencyContact.scope == "NATIONAL", EmergencyContact.label == label
            )
        )
        if existing:
            existing.phone = phone
            existing.description = desc
        else:
            db.add(
                EmergencyContact(
                    scope="NATIONAL", state_id=None, city_id=None,
                    label=label, phone=phone, description=desc,
                )
            )

    # City facilities (idempotent on city+name)
    cities = {c.slug: c for c in (await db.scalars(select(City))).all()}
    for city_slug, facilities in FACILITIES_BY_CITY.items():
        city = cities.get(city_slug)
        if city is None:
            continue
        for name, kind, address, phone, is24, lat, lng in facilities:
            existing = await db.scalar(
                select(EmergencyFacility).where(
                    EmergencyFacility.city_id == city.id,
                    EmergencyFacility.name == name,
                )
            )
            if existing:
                existing.phone = phone
                existing.is_24x7 = is24
            else:
                db.add(
                    EmergencyFacility(
                        city_id=city.id, name=name, kind=kind, address=address,
                        phone=phone, is_24x7=is24, latitude=lat, longitude=lng,
                    )
                )
    await db.commit()


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await seed(db)
    print("safety seed complete")


if __name__ == "__main__":
    asyncio.run(main())
