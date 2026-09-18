"""Seed editorial place details (explore detail pages).

Idempotent: overwrites `places.details` for the listed slugs on every run.
All content is DEMO/EDITORIAL data authored for the SIH MVP demo (design doc
D12: seed data is data, the schema stays location-agnostic). Reviews embedded
here are SAMPLE reviews for layout demonstration, not real traveller
submissions — the PlaceReview system arrives in a later phase. Nearby slugs
are resolved against live places by the API, so unknown slugs are dropped.

Run:  ./.venv/Scripts/python.exe -m scripts.seed_place_details
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal as SessionLocal
from app.models.geo import Place

# Image paths are relative to the web app's /public root.
DETAILS: dict[str, dict] = {
    "chilika-lake-satapada-side": {
        "tagline": "Dolphins, birds, backwaters and a quieter side of India's largest brackish water lagoon.",
        "eyebrow": "NATURE · WILDLIFE",
        "accent_script": "Wilder · Quieter · More Real",
        "about_heading": "A meeting point of waters and wilderness.",
        "about_body": (
            "Chilika Lake, Asia's largest brackish water lagoon, is a dynamic blend of lake, "
            "river and sea. The Satapada side, about 50 km from Puri, is the quieter, unspoiled "
            "part of Chilika. Here, you can spot playful Irrawaddy dolphins, watch migratory "
            "birds, and take boats through serene backwaters and small islands — far from the "
            "usual crowds of the more commercialized Barkul side."
        ),
        "experience_note": "Same waters. A different story.",
        "photo_note": "Frames from the journey",
        "experiences": [
            {"title": "Dolphin Watching", "description": "Spot the rare Irrawaddy dolphins in their natural habitat."},
            {"title": "Bird Watching", "description": "Home to hundreds of migratory and resident bird species."},
            {"title": "Boating", "description": "Explore backwaters, small islands and fishing villages."},
            {"title": "Island Hopping", "description": "Visit Nalabana (seasonal), Honeymoon Island and other scenic spots."},
        ],
        "travel_tips": [
            "Book boats through registered operators.",
            "Carry sunglasses, sunscreen and a hat.",
            "Wear comfortable clothing and footwear.",
            "Respect wildlife and avoid disturbing dolphins.",
            "Check weather conditions before planning.",
            "Avoid plastic and help keep the lake clean.",
        ],
        "travel_info": {
            "location": "Satapada, Puri, Odisha",
            "distance": "~ 50 km (1.5 – 2 hours by road) from Puri",
            "best_time": "October – March",
            "weather": "15°C – 30°C · Pleasant and ideal for boating",
            "ideal_for": "Nature lovers, photographers, families, solo travellers",
        },
        "gallery_caption": "Boat ride into the lagoon at first light.",
        "gallery": [
            {"url": "/images/places/chilika-lake-satapada-side/gallery-1.jpg", "caption": "Dolphins surfacing in the channel"},
            {"url": "/images/places/chilika-lake-satapada-side/gallery-2.jpg", "caption": "Migratory birds on the mudflats"},
            {"url": "/images/places/chilika-lake-satapada-side/gallery-3.jpg", "caption": "Backwater channels and small islands"},
            {"url": "/images/places/chilika-lake-satapada-side/gallery-4.jpg", "caption": "Sunset over the lagoon"},
            {"url": "/images/places/chilika-lake-satapada-side/gallery-5.jpg", "caption": "Fisher boats moored at Satapada"},
        ],
        "sample_reviews": [
            {
                "author": "Ananya S.",
                "rating": 5,
                "visited": "Jan 2024",
                "text": "The Satapada side is absolutely worth it. Peaceful, beautiful and the dolphin sighting was magical. So different from the crowded Puri Beach.",
            },
        ],
        "nearby": [
            {"slug": "raghurajpur-heritage-village", "label": "~ 40 km"},
            {"slug": "baliharachandi-beach", "label": "~ 45 km"},
            {"slug": "puri-beach-swargadwar-stretch", "label": "~ 50 km"},
        ],
    },
    "raghurajpur-heritage-village": {
        "tagline": "A village where every home is an artist's studio.",
        "eyebrow": "CULTURE · ART · HERITAGE",
        "accent_script": "Art lives here.",
        "about_heading": "A village of art, tradition and living heritage.",
        "about_body": (
            "Just 12 km from Puri, Raghurajpur is a unique artisan village where every house "
            "has at least one Pattachitra artist. This heritage village keeps Odisha's "
            "traditional art forms alive — from intricate scroll paintings to palm leaf "
            "engravings, tussar painting, wood carving and more. The villagers are warm and "
            "welcoming, often inviting visitors into their homes to witness the creation of "
            "art that has been passed down for generations."
        ),
        "experience_note": "Not just a destination, but a living tradition.",
        "photo_note": "Art in every frame",
        "experiences": [
            {"title": "Pattachitra Art", "description": "Watch artists create intricate scroll paintings."},
            {"title": "Palm Leaf Engraving", "description": "See ancient stories carved on palm leaves."},
            {"title": "Tussar Painting", "description": "Explore unique art on silk fabric."},
            {"title": "Wood Carving", "description": "Beautiful wooden sculptures and toys."},
            {"title": "Meet the Artists", "description": "Interact with local artisans and learn their stories."},
        ],
        "travel_tips": [
            "Be respectful while visiting artists' homes.",
            "Ask before taking photographs.",
            "You can buy authentic artwork directly from the artists.",
            "Carry cash as digital payment options may be limited.",
            "Wear comfortable clothing and footwear.",
            "Combine your visit with nearby places like Pipili or Puri.",
        ],
        "travel_info": {
            "location": "Raghurajpur, Puri, Odisha",
            "distance": "~ 12 km (30 – 40 minutes by road) from Puri",
            "best_time": "October – March",
            "weather": "20°C – 32°C · Pleasant and ideal for exploring",
            "ideal_for": "Art lovers, culture seekers, families, photographers",
        },
        "gallery_caption": "Every wall tells a story.",
        "gallery": [
            {"url": "/images/places/raghurajpur-heritage-village/gallery-1.jpg", "caption": "Fine Pattachitra brushwork"},
            {"url": "/images/places/raghurajpur-heritage-village/gallery-2.jpg", "caption": "The artist at work"},
            {"url": "/images/places/raghurajpur-heritage-village/gallery-3.jpg", "caption": "Traditional painted masks"},
            {"url": "/images/places/raghurajpur-heritage-village/gallery-4.jpg", "caption": "Scrolls drying in the courtyard"},
            {"url": "/images/places/raghurajpur-heritage-village/gallery-5.jpg", "caption": "Village lanes lined with art"},
        ],
        "sample_reviews": [
            {
                "author": "Sneha R.",
                "rating": 5,
                "visited": "Feb 2024",
                "text": "An incredible experience! The artists are so warm and talented. It felt like stepping into a different world.",
            },
        ],
        "nearby": [
            {"slug": "puri-beach-swargadwar-stretch", "label": "~ 12 km"},
            {"slug": "chilika-lake-satapada-side", "label": "~ 50 km"},
            {"slug": "baliharachandi-beach", "label": "~ 40 km"},
        ],
    },
    "baliharachandi-beach": {
        "tagline": "Where river meets the ocean, and nature meets divinity.",
        "eyebrow": "BEACH · SPIRITUAL · NATURE",
        "accent_script": "Same Waves · Different Peace",
        "about_heading": "A quiet beach with a deeper story.",
        "about_body": (
            "Located about 27 km from Puri, Baliharachandi Beach is a serene and relatively "
            "unexplored destination where the Nuanai river meets the Bay of Bengal. With its "
            "clean sands, rolling dunes and breathtaking sunsets, it offers a peaceful escape "
            "from the crowds of Puri Beach. Perched on a dune overlooking the ocean is the "
            "Baliharachandi Temple, dedicated to Goddess Durga, adding a spiritual charm to "
            "the natural beauty."
        ),
        "experience_note": "Where the river meets the ocean…",
        "photo_note": "Sunsets, dunes and divinity",
        "experiences": [
            {"title": "Serene Beach", "description": "A clean, uncrowded beach perfect for long walks."},
            {"title": "Stunning Sunsets", "description": "Breathtaking views where the river meets the ocean."},
            {"title": "Baliharachandi Temple", "description": "A spiritual experience with a divine view."},
            {"title": "Sand Dunes", "description": "Explore scenic dunes overlooking the coast."},
            {"title": "Photography", "description": "A paradise for landscape and drone photography."},
        ],
        "travel_tips": [
            "Carry water, snacks, sunscreen and a hat.",
            "Wear comfortable clothing and footwear.",
            "Check weather conditions before planning.",
            "Respect the temple premises and local customs.",
            "Avoid littering and help keep the beach clean.",
            "Best experienced during sunrise or sunset.",
        ],
        "travel_info": {
            "location": "Baliharachandi, Puri, Odisha",
            "distance": "~ 27 km (45 – 60 minutes by road) from Puri",
            "best_time": "October – March",
            "weather": "20°C – 32°C · Pleasant and ideal for beach walks",
            "ideal_for": "Beach lovers, photographers, spiritual travellers, peace seekers",
        },
        "gallery_caption": "Two waters, one horizon.",
        "gallery": [
            {"url": "/images/places/baliharachandi-beach/gallery-1.jpg", "caption": "Sunset over the river mouth"},
            {"url": "/images/places/baliharachandi-beach/gallery-2.jpg", "caption": "The temple on the dune"},
            {"url": "/images/places/baliharachandi-beach/gallery-3.jpg", "caption": "Aerial view of river and sea"},
            {"url": "/images/places/baliharachandi-beach/gallery-4.jpg", "caption": "Evening light on wet sand"},
            {"url": "/images/places/baliharachandi-beach/gallery-5.jpg", "caption": "The estuary from the dunes"},
        ],
        "sample_reviews": [
            {
                "author": "Aditi R.",
                "rating": 5,
                "visited": "Jan 2024",
                "text": "A hidden gem near Puri. The beach is so peaceful and the sunset is magical. The temple on the dune makes it even more special.",
            },
        ],
        "nearby": [
            {"slug": "puri-beach-swargadwar-stretch", "label": "~ 27 km"},
            {"slug": "chilika-lake-satapada-side", "label": "~ 60 km"},
            {"slug": "raghurajpur-heritage-village", "label": "~ 40 km"},
        ],
    },
}


async def seed(db: AsyncSession) -> dict:
    updated = 0
    for slug, payload in DETAILS.items():
        place = (
            await db.scalars(select(Place).where(Place.slug == slug))
        ).first()
        if place is None:
            print(f"  ! place not found, skipping: {slug}")
            continue
        place.details = payload
        updated += 1
    await db.commit()
    return {"updated": updated}


async def main() -> None:
    async with SessionLocal() as db:
        result = await seed(db)
        print(f"Place details seeded: {result['updated']} places updated (demo editorial data).")


if __name__ == "__main__":
    asyncio.run(main())
