"""Trip companions + avatar endpoints (Phase 8a).

Companionship is the "travelling together" sharing feature: the trip head
invites other VIRĀM accounts, invitees accept/decline, and accepted
companions get read-only access to the shared itinerary — never to the
head's bookings or payments (design doc §24: OWNER_ONLY data stays owner-only;
sharing is an explicit, revocable grant).

Ownership rules:
- Only the trip head invites or removes companions.
- Only the invited account accepts/declines its own invitations.
- Trip reads are per-user; this module contributes an overlay: the trip detail
  endpoint accepts companions of the trip as read-only viewers.
"""

import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.modules.planning import companions_service
from app.modules.users.deps import get_current_user

router = APIRouter(tags=["companions"])


class InviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


@router.post("/trips/{trip_id}/companions", status_code=status.HTTP_201_CREATED)
async def invite_companion(
    trip_id: uuid.UUID,
    payload: InviteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await companions_service.invite(db, user=user, trip_id=trip_id, email=payload.email)
    await db.commit()
    u = await db.get(User, row.companion_user_id)
    return {
        "id": str(row.id),
        "trip_id": str(row.trip_id),
        "companion_user_id": str(row.companion_user_id),
        "companion_name": u.display_name if u else "Traveller",
        "status": row.status,
    }


@router.get("/trips/{trip_id}/companions")
async def list_companions(
    trip_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = await companions_service.list_for_trip(db, user=user, trip_id=trip_id)
    return {"items": items}


@router.delete("/trips/{trip_id}/companions/{companion_row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_companion(
    trip_id: uuid.UUID,
    companion_row_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await companions_service.remove(db, user=user, trip_id=trip_id, row_id=companion_row_id)
    await db.commit()


@router.get("/companions/invitations")
async def my_invitations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = await companions_service.invitations_for(db, user=user)
    return {"items": items}


@router.get("/companions/shared")
async def shared_with_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trips this traveller follows as an accepted companion."""
    items = await companions_service.shared_trips_for(db, user=user)
    return {"items": items}


@router.post("/companions/invitations/{row_id}/accept")
async def accept_invitation(
    row_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = await companions_service.respond(db, user=user, row_id=row_id, accept=True)
    await db.commit()
    return item


@router.post("/companions/invitations/{row_id}/decline")
async def decline_invitation(
    row_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = await companions_service.respond(db, user=user, row_id=row_id, accept=False)
    await db.commit()
    return item
