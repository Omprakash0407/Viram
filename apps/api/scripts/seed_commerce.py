"""Seed demo commerce data for Odisha: hotels + room types + guides.

Idempotent: safe to re-run (upserts on natural keys). This is DEMO data —
hotels are admin-managed (design D7) so seeding stands in for the admin
onboarding flow; guide profiles are owned by dedicated demo users whose
accounts exist only to hold the provider capability (D1: a guide is a USER
with an approved guide_profiles row).

Rates/prices are editorial demo values, not live market data (D6: the platform
never claims real availability or live pricing).

Run:  ./.venv/Scripts/python.exe -m scripts.seed_commerce
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.commerce import GuideAvailability, GuideProfile, Hotel, RoomType
from app.models.providers import BusinessProfile
from app.models.user import User

# (slug, name, description, amenities, public_address, phone)
HOTELS: list[tuple] = [
    (
        "mayfair-lagoon-bbsr",
        "Mayfair Lagoon",
        "Upscale resort hotel set around a lagoon, close to the city's temple circuit.",
        ["pool", "spa", "wifi", "breakfast", "parking"],
        "Jaydev Vihar, Bhubaneswar",
        "+91 674 000 0001",
    ),
    (
        "hotel-sandy-tower-puri",
        "Hotel Sandy Tower",
        "Beachside hotel a short walk from the Puri seafront and temple lane.",
        ["wifi", "sea view", "breakfast", "restaurant"],
        "Chakratirtha Road, Puri",
        "+91 6752 000 002",
    ),
    (
        "chilika-boutique-stay",
        "Chilika Boutique Stay",
        "Small lakeside stay convenient for Satapada dolphin-point boat trips.",
        ["wifi", "lakeside", "boat desk", "home-style food"],
        "Satapada Road, Puri district",
        "+91 6752 000 003",
    ),
]

# per hotel slug: [(room name, capacity, nightly paise, declared units)]
ROOMS: dict[str, list[tuple]] = {
    "mayfair-lagoon-bbsr": [
        ("Deluxe Double", 2, 7_500_00, 12),
        ("Executive Suite", 3, 14_000_00, 4),
    ],
    "hotel-sandy-tower-puri": [
        ("Sea View Double", 2, 4_200_00, 10),
        ("Family Room", 4, 6_800_00, 6),
    ],
    "chilika-boutique-stay": [
        ("Lakeside Cottage", 2, 3_500_00, 5),
    ],
}

# (email, public_name, bio, languages, expertise, areas, city slug, day rate paise)
GUIDES: list[tuple] = [
    (
        "guide.puri@viramdemo.com",
        "Saroj Das",
        "Puri-based cultural guide; Pattachitra and temple-heritage walks, Raghurajpur artisan visits.",
        ["Odia", "Hindi", "English"],
        ["temple heritage", "craft villages", "food walks"],
        ["Puri", "Raghurajpur", "Satapada"],
        "puri",
        2_500_00,
    ),
    (
        "guide.bbsr@viramdemo.com",
        "Ankita Mohanty",
        "Bhubaneswar city specialist: Khandagiri caves, tribal museum, food streets.",
        ["Odia", "Hindi", "English", "Bengali"],
        ["city heritage", "museums", "street food"],
        ["Bhubaneswar", "Udayagiri", "Khandagiri"],
        "bhubaneswar",
        2_200_00,
    ),
    (
        "guide.chilika@viramdemo.com",
        "Rakesh Behera",
        "Chilika naturalist guide for birding and dolphin-point boat trips on the Satapada side.",
        ["Odia", "Hindi"],
        ["birding", "lagoon ecology", "boat trips"],
        ["Chilika", "Satapada", "Barkul"],
        "puri",
        3_000_00,
    ),
]

AVAIL_DAYS = 60  # guides offer every date for the next 60 days except markers below

# Local Partners demo data (§17): verified Odisha businesses for the partners
# wall and directory. (email, business name, category, description, services,
# public address, phone, city slug, optional place slug)
BUSINESSES: list[tuple] = [
    (
        "business.pattachitra@viramdemo.com",
        "Raghurajpur Pattachitra Studio",
        "ARTISAN",
        "Family workshop in the heritage village of Raghurajpur — every house here has a living Pattachitra artist. Buy directly from the painter who made it.",
        ["Pattachitra paintings", "palm-leaf engravings", "artisan visits"],
        "Raghurajpur Heritage Village, Puri district",
        "+91 6752 000 010",
        "puri",
        "raghurajpur-heritage-village",
    ),
    (
        "business.pipli-applique@viramdemo.com",
        "Pipli Applied Art Collective",
        "HANDICRAFT",
        "Cooperative of appliqué artisans from Pipli, the village whose canopies and lamp shades travel to festivals across India.",
        ["appliqué wall hangings", "lamp shades", "custom orders"],
        "Pipli Bazaar, NH-16, between Bhubaneswar and Puri",
        "+91 674 000 011",
        "bhubaneswar",
        None,
    ),
    (
        "business.niladri-cafe@viramdemo.com",
        "Niladri Coffee House",
        "CAFE",
        "Old-school Puri coffee house a short walk from the temple lane — filter coffee, cutlets and a quiet corner.",
        ["filter coffee", "snacks", "breakfast"],
        "Grand Road, Puri",
        "+91 6752 000 012",
        "puri",
        None,
    ),
    (
        "business.dalma-kitchen@viramdemo.com",
        "Dalma Kitchen",
        "RESTAURANT",
        "Home-style Odia food: dalma, machha besara, pakhal bhata — cooked the way Bhubaneswar families eat.",
        ["Odia thali", "vegetarian", "family seating"],
        "Saheed Nagar, Bhubaneswar",
        "+91 674 000 013",
        "bhubaneswar",
        None,
    ),
    (
        "business.satapada-boats@viramdemo.com",
        "Satapada Boat Cooperative",
        "TOUR",
        "Licensed boatmen's cooperative on the Satapada side of Chilika — dolphin-point trips and backwater island routes, far from the crowds.",
        ["dolphin-point boating", "island hopping", "birding trips"],
        "Satapada Jetty, Chilika",
        "+91 6752 000 014",
        "chilika-satapada",
        "chilika-lake-satapada-dolphin-and-bird-watching",
    ),
    (
        "business.daringbadi-stay@viramdemo.com",
        "Daringbadi Pine Homestay",
        "HOMESTAY",
        "Family homestay among the pine groves of the Kashmir of Odisha — hill-view rooms, bonfires and local meals.",
        ["hill-view rooms", "bonfire evenings", "home-cooked meals"],
        "Daringbadi, Kandhamal district",
        "+91 6846 000 015",
        "daringbadi",
        None,
    ),
]


async def upsert_hotels() -> None:
    from app.models.geo import City

    async with AsyncSessionLocal() as db:
        cities = {
            c.slug: c for c in (await db.scalars(select(City))).all()
        }
        bbsr = cities.get("bhubaneswar")
        puri = cities.get("puri")
        if bbsr is None or puri is None:
            raise SystemExit("Run scripts.seed_odisha first (cities missing).")

        hotel_city = {
            "mayfair-lagoon-bbsr": bbsr,
            "hotel-sandy-tower-puri": puri,
            "chilika-boutique-stay": puri,
        }

        for slug, name, desc, amenities, address, phone in HOTELS:
            hotel = await db.scalar(select(Hotel).where(Hotel.slug == slug))
            if hotel is None:
                hotel = Hotel(
                    city_id=hotel_city[slug].id,
                    name=name,
                    slug=slug,
                    description=desc,
                    amenities=amenities,
                    public_phone=phone,
                    public_address=address,
                    status="ACTIVE",
                )
                db.add(hotel)
                await db.flush()
                print(f"+ hotel {name}")
            else:
                hotel.description = desc
                hotel.amenities = amenities
                hotel.public_address = address
                print(f"~ hotel {name} (updated)")

            for room_name, capacity, paise, units in ROOMS[slug]:
                room = await db.scalar(
                    select(RoomType).where(RoomType.hotel_id == hotel.id, RoomType.name == room_name)
                )
                if room is None:
                    db.add(
                        RoomType(
                            hotel_id=hotel.id,
                            name=room_name,
                            capacity=capacity,
                            nightly_rate_paise=paise,
                            declared_units=units,
                        )
                    )
                    print(f"  + room {room_name}")
                else:
                    room.nightly_rate_paise = paise
                    room.capacity = capacity
                    print(f"  ~ room {room_name} (updated)")
        await db.commit()


async def upsert_guides() -> None:
    from app.models.geo import City

    async with AsyncSessionLocal() as db:
        cities = {c.slug: c for c in (await db.scalars(select(City))).all()}

        # one demo user per guide (capability owner; contact lives on the account, §3)
        for email, public_name, bio, langs, expertise, areas, city_slug, rate in GUIDES:
            user = await db.scalar(select(User).where(User.email == email))
            if user is None:
                from app.core.security import hash_password

                user = User(
                    email=email,
                    password_hash=hash_password("GuideDemo#2026"),
                    display_name=public_name,
                    account_role="USER",
                    status="ACTIVE",
                )
                db.add(user)
                await db.flush()
                print(f"+ user {email}")

            guide = await db.scalar(select(GuideProfile).where(GuideProfile.user_id == user.id))
            if guide is None:
                guide = GuideProfile(
                    user_id=user.id,
                    public_name=public_name,
                    bio=bio,
                    languages=langs,
                    expertise=expertise,
                    areas_served=areas,
                    city_id=cities[city_slug].id,
                    day_rate_paise=rate,
                    status="APPROVED",
                    visibility="PUBLIC",
                    reviewed_at=None,
                )
                db.add(guide)
                await db.flush()
                print(f"+ guide {public_name}")
            else:
                guide.bio = bio
                guide.day_rate_paise = rate
                guide.status = "APPROVED"
                guide.visibility = "PUBLIC"
                print(f"~ guide {public_name} (updated)")

            today = date.today()
            existing = set(
                (
                    await db.scalars(
                        select(GuideAvailability.service_date).where(
                            GuideAvailability.guide_profile_id == guide.id
                        )
                    )
                ).all()
            )
            added = 0
            for i in range(AVAIL_DAYS):
                d = today + timedelta(days=i)
                if d in existing:
                    continue
                db.add(GuideAvailability(guide_profile_id=guide.id, service_date=d, status="AVAILABLE"))
                added += 1
            if added:
                print(f"  + {added} availability rows")
        await db.commit()


async def upsert_businesses() -> None:
    """Seed verified Local Partners (§17). Owners are dedicated demo users; the
    approved status stands in for the admin verification flow (same as guides)."""
    from app.models.geo import City, Place, State

    async with AsyncSessionLocal() as db:
        state = await db.scalar(select(State))
        cities = {c.slug: c for c in (await db.scalars(select(City))).all()}
        places = {p.slug: p for p in (await db.scalars(select(Place))).all()}
        if state is None or not cities:
            raise SystemExit("Run scripts.seed_odisha first (states/cities missing).")

        for (email, name, category, desc, services, address, phone, city_slug,
             place_slug) in BUSINESSES:
            user = await db.scalar(select(User).where(User.email == email))
            if user is None:
                from app.core.security import hash_password

                user = User(
                    email=email,
                    password_hash=hash_password("BusinessDemo#2026"),
                    display_name=name,
                    account_role="USER",
                    status="ACTIVE",
                )
                db.add(user)
                await db.flush()
                print(f"+ user {email}")

            biz = await db.scalar(
                select(BusinessProfile).where(
                    BusinessProfile.user_id == user.id, BusinessProfile.name == name
                )
            )
            if biz is None:
                biz = BusinessProfile(
                    user_id=user.id,
                    name=name,
                    description=desc,
                    category=category,
                    state_id=state.id,
                    city_id=cities[city_slug].id,
                    place_id=places[place_slug].id if place_slug else None,
                    services=services,
                    public_phone=phone,
                    public_address=address,
                    status="APPROVED",
                    visibility="PUBLIC",
                )
                db.add(biz)
                await db.flush()
                print(f"+ business {name}")
            else:
                biz.description = desc
                biz.services = services
                biz.public_address = address
                biz.status = "APPROVED"
                biz.visibility = "PUBLIC"
                print(f"~ business {name} (updated)")
        await db.commit()


async def main() -> None:
    await upsert_hotels()
    await upsert_guides()
    await upsert_businesses()
    print("commerce seed complete")


if __name__ == "__main__":
    asyncio.run(main())
