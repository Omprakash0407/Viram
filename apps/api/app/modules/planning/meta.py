"""Planning flow metadata (mock steps 3, 4, 7, 8, 9).

Static reference data for the 12-step wizard. Deliberately served from code
(not DB) for the MVP: it is presentational copy, not domain data — no schema
impact, and D12 (no hardcoded location data) is not violated because these
are not location-specific facts.
"""

from fastapi import APIRouter

from app.modules.planning.schemas import BUDGET_TIERS, MOODS

router = APIRouter(prefix="/planning", tags=["planning"])

ESSENTIALS = [
    {"category": "Clothing (season wise)", "items": ["Light layers", "Warm layer for hills", "Rain jacket"]},
    {"category": "Footwear", "items": ["Comfortable walking shoes", "Sandals"]},
    {"category": "Medicines & First Aid", "items": ["Personal prescriptions", "Basic first-aid kit"]},
    {"category": "Documents (ID, bookings)", "items": ["Government ID", "Booking confirmations"]},
    {"category": "Electronics & Chargers", "items": ["Phone charger", "Power bank"]},
    {"category": "Others", "items": ["Sunscreen", "Water bottle"]},
]

PRECAUTIONS = [
    "Check weather conditions before travel",
    "Keep your documents safe",
    "Stay hydrated",
    "Avoid isolated areas after dark",
    "Follow local rules & culture",
]

REMINDERS = [
    {"offset_days": 10, "title": "10 Days Before Trip", "detail": "Welcome message + checklist"},
    {"offset_days": 7, "title": "7 Days Before", "detail": "Safety tips & health guidelines"},
    {"offset_days": 5, "title": "5 Days Before", "detail": "Documents & travel details"},
    {"offset_days": 1, "title": "1 Day Before", "detail": "Final reminder + weather update"},
]


@router.get("/moods")
async def list_moods() -> dict:
    return {"items": [{"key": m, "label": m.replace("_", " ").title()} for m in MOODS]}


@router.get("/budget-tiers")
async def list_budget_tiers() -> dict:
    labels = {
        "BUDGET": "Comfortable & value for money",
        "MODERATE": "Comfortable & well-balanced",
        "PREMIUM": "More comfort & luxury",
        "EXECUTIVE": "VIP & exclusive experiences",
    }
    return {"items": [{"key": t, "label": labels[t]} for t in BUDGET_TIERS]}


@router.get("/essentials")
async def list_essentials() -> dict:
    return {"items": ESSENTIALS}


@router.get("/precautions")
async def list_precautions() -> dict:
    return {"items": PRECAUTIONS}


@router.get("/reminders")
async def list_reminders() -> dict:
    return {"items": REMINDERS}
