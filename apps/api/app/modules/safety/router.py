"""Safety module: emergency facilities + contacts (design doc §29) — public read."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.intelligence import EmergencyContact, EmergencyFacility

router = APIRouter(prefix="/emergency", tags=["emergency"])


@router.get("/facilities")
async def list_facilities(
    city_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Emergency facilities for one city (admin/seed managed, never user content)."""
    rows = (
        await db.scalars(
            select(EmergencyFacility)
            .where(EmergencyFacility.city_id == city_id)
            .order_by(EmergencyFacility.kind, EmergencyFacility.name)
        )
    ).all()
    return {
        "items": [
            {
                "id": str(f.id),
                "name": f.name,
                "kind": f.kind,
                "address": f.address,
                "phone": f.phone,
                "is_24x7": f.is_24x7,
                "latitude": float(f.latitude),
                "longitude": float(f.longitude),
            }
            for f in rows
        ]
    }


@router.get("/contacts")
async def list_contacts(
    state_id: str | None = None,
    city_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Emergency numbers: national always, plus matching state/city rows."""
    rows = (await db.scalars(select(EmergencyContact))).all()
    items = [
        {
            "id": str(c.id),
            "scope": c.scope,
            "label": c.label,
            "phone": c.phone,
            "description": c.description,
        }
        for c in rows
        if c.scope == "NATIONAL"
        or (c.scope == "STATE" and state_id and str(c.state_id) == state_id)
        or (c.scope == "CITY" and city_id and str(c.city_id) == city_id)
    ]
    return {"items": items}
