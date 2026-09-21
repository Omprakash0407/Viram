"""Community suggestions (§14) + admin audit logging (§32).

Core rule: submissions are NEVER auto-published. They land PENDING, are
visible only to admins, and an approval/rejection records reviewer, timestamp
and note in the row itself plus an append-only AdminAuditLog entry.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.exceptions import ValidationError as AppValidationError
from app.models.commerce import AdminAuditLog
from app.models.geo import City, Place
from app.models.intelligence import CommunitySuggestion
from app.models.user import User
from app.modules.admin.schemas import SuggestionCreate

SUGGESTION_KINDS = {
    "RITUAL", "TRADITION", "FOOD", "CRAFT", "FAIR_FESTIVAL",
    "PLACE", "HISTORY", "EXPERIENCE", "OTHER",
}


async def _audit(
    db: AsyncSession, *, admin: User, action: str, target: CommunitySuggestion, note: str | None
) -> None:
    db.add(
        AdminAuditLog(
            admin_id=admin.id,
            action=action,
            target_type="community_suggestion",
            target_id=target.id,
            before={"status": "PENDING"} if action == "APPROVE_SUGGESTION" else None,
            after={"status": target.status, "note": note},
        )
    )


async def create_suggestion(
    db: AsyncSession, *, payload: SuggestionCreate
) -> CommunitySuggestion:
    """Public intake — anonymous visitors can submit local knowledge."""
    kind = payload.kind.strip().upper()
    if kind not in SUGGESTION_KINDS:
        raise AppValidationError(
            f"kind must be one of {sorted(SUGGESTION_KINDS)}"
        )
    city_id = payload.city_id
    if city_id is not None and await db.get(City, city_id) is None:
        raise NotFoundError("City not found.")
    place_id = payload.place_id
    if place_id is not None and await db.get(Place, place_id) is None:
        raise NotFoundError("Place not found.")

    suggestion = CommunitySuggestion(
        submitter_name=payload.submitter_name,
        contact=payload.contact,
        kind=kind,
        # The public endpoint is the in-app channel (§22); the Google Form
        # import writes rows with the GOOGLE_FORM default directly.
        source="IN_APP",
        state_id=None,
        city_id=city_id,
        place_id=place_id,
        title=payload.title,
        body=payload.body,
        status="PENDING",
    )
    db.add(suggestion)
    await db.flush()
    return suggestion


async def list_suggestions(
    db: AsyncSession, *, admin: User, status: str | None
) -> list[CommunitySuggestion]:
    if admin.account_role != "ADMIN":
        raise PermissionDeniedError("Admins only.")
    stmt = select(CommunitySuggestion).order_by(CommunitySuggestion.created_at.desc()).limit(200)
    if status:
        stmt = stmt.where(CommunitySuggestion.status == status.upper())
    return list((await db.scalars(stmt)).all())


async def review_suggestion(
    db: AsyncSession, *, admin: User, suggestion_id: uuid.UUID, decision: str, note: str | None
) -> CommunitySuggestion:
    if admin.account_role != "ADMIN":
        raise PermissionDeniedError("Admins only.")
    suggestion = await db.get(CommunitySuggestion, suggestion_id)
    if suggestion is None:
        raise NotFoundError("Suggestion not found.")
    if suggestion.status != "PENDING":
        raise AppValidationError("This suggestion has already been reviewed.")

    decision = decision.strip().upper()
    if decision not in ("APPROVED", "REJECTED"):
        raise AppValidationError("decision must be APPROVED or REJECTED")

    suggestion.status = decision
    suggestion.admin_note = note
    suggestion.reviewed_by = admin.id
    suggestion.reviewed_at = func_now()
    await _audit(
        db,
        admin=admin,
        action="APPROVE_SUGGESTION" if decision == "APPROVED" else "REJECT_SUGGESTION",
        target=suggestion,
        note=note,
    )
    await db.flush()
    return suggestion


def func_now():
    from sqlalchemy import func

    return func.now()
