"""Provider services: guide/business profiles, verification, Local Partners (§4, §5, §17).

Rules enforced here:
- Verification is entity-level status (§5): PENDING → APPROVED | REJECTED,
  APPROVED → SUSPENDED → APPROVED. Every decision stamps reviewer/time/note on
  the row AND writes an append-only AdminAuditLog entry (§23).
- Public discovery serves only status='APPROVED' AND visibility='PUBLIC' rows.
- Owners manage only their own rows (row-level ownership, §2).
- Guide profile is 0..1 per user; businesses are 0..N per user.
- Identity verification status is derived from identity_verifications — a
  guide/business owner's identity is surfaced to admins in the queue.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.exceptions import ValidationError as AppValidationError
from app.models.commerce import GuideProfile
from app.models.commerce import AdminAuditLog
from app.models.geo import City, Place
from app.models.providers import BUSINESS_CATEGORIES, BusinessProfile
from app.models.user import User
from app.modules.providers.schemas import (
    BusinessProfileCreate,
    BusinessProfileUpdate,
    GuideProfileUpsert,
)

PUBLIC_FILTER = "status = 'APPROVED' AND visibility = 'PUBLIC'"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _audit(
    db: AsyncSession, *, admin: User, action: str, target_type: str,
    target_id: uuid.UUID, before: dict | None, after: dict | None, note: str | None,
) -> None:
    db.add(
        AdminAuditLog(
            admin_id=admin.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            reason=note,
        )
    )


# ---------- Guide profile ----------

async def get_or_init_guide(db: AsyncSession, *, user: User) -> GuideProfile | None:
    return await db.scalar(select(GuideProfile).where(GuideProfile.user_id == user.id))


async def upsert_guide(
    db: AsyncSession, *, user: User, payload: GuideProfileUpsert
) -> GuideProfile:
    """Create or update the caller's single guide profile.

    A resubmit after REJECTED returns the profile to PENDING for re-review;
    an APPROVED profile keeps its status on minor edits (re-verification of
    content edits is an admin policy decision for a later phase).
    """
    if payload.city_id is not None and await db.get(City, payload.city_id) is None:
        raise NotFoundError("City not found.")

    guide = await get_or_init_guide(db, user=user)
    if guide is None:
        guide = GuideProfile(user_id=user.id, public_name=payload.public_name.strip())
        db.add(guide)
    elif guide.status == "REJECTED":
        guide.status = "PENDING"
        guide.reviewed_by = None
        guide.reviewed_at = None
        guide.review_note = None

    guide.public_name = payload.public_name.strip()
    guide.bio = payload.bio
    guide.languages = [s.strip() for s in payload.languages if s.strip()]
    guide.expertise = [s.strip() for s in payload.expertise if s.strip()]
    guide.areas_served = [s.strip() for s in payload.areas_served if s.strip()]
    guide.city_id = payload.city_id
    guide.day_rate_paise = payload.day_rate_paise
    await db.flush()
    return guide


async def list_public_guides(
    db: AsyncSession, *, city_id: uuid.UUID | None, limit: int, offset: int
) -> tuple[list[GuideProfile], int]:
    stmt = select(GuideProfile).where(GuideProfile.status == "APPROVED")
    count_stmt = select(func.count()).select_from(GuideProfile).where(GuideProfile.status == "APPROVED")
    if city_id is not None:
        stmt = stmt.where(GuideProfile.city_id == city_id)
        count_stmt = count_stmt.where(GuideProfile.city_id == city_id)
    stmt = stmt.order_by(GuideProfile.created_at.desc()).limit(limit).offset(offset)
    rows = list((await db.scalars(stmt)).all())
    total = (await db.scalar(count_stmt)) or 0
    return rows, total


# ---------- Business profile ----------

async def create_business(
    db: AsyncSession, *, user: User, payload: BusinessProfileCreate
) -> BusinessProfile:
    category = payload.category.strip().upper()
    if category not in BUSINESS_CATEGORIES:
        raise AppValidationError(f"category must be one of {list(BUSINESS_CATEGORIES)}")

    city = await db.get(City, payload.city_id)
    if city is None:
        raise NotFoundError("City not found.")
    if payload.place_id is not None and await db.get(Place, payload.place_id) is None:
        raise NotFoundError("Place not found.")

    business = BusinessProfile(
        user_id=user.id,
        name=payload.name.strip(),
        description=payload.description,
        category=category,
        state_id=city.state_id,
        city_id=city.id,
        place_id=payload.place_id,
        services=[s.strip() for s in payload.services if s.strip()],
        public_phone=payload.public_phone,
        public_email=payload.public_email,
        public_address=payload.public_address,
        status="PENDING",
        visibility="PRIVATE",
    )
    db.add(business)
    await db.flush()
    return business


async def list_my_businesses(db: AsyncSession, *, user: User) -> list[BusinessProfile]:
    stmt = (
        select(BusinessProfile)
        .where(BusinessProfile.user_id == user.id)
        .order_by(BusinessProfile.created_at.desc())
    )
    return list((await db.scalars(stmt)).all())


async def get_own_business(
    db: AsyncSession, *, user: User, business_id: uuid.UUID
) -> BusinessProfile:
    business = await db.get(BusinessProfile, business_id)
    if business is None:
        raise NotFoundError("Business not found.")
    if business.user_id != user.id:
        raise PermissionDeniedError("You do not own this business profile.")
    return business


async def update_business(
    db: AsyncSession, *, user: User, business_id: uuid.UUID, payload: BusinessProfileUpdate
) -> BusinessProfile:
    business = await get_own_business(db, user=user, business_id=business_id)
    data = payload.model_dump(exclude_unset=True)
    if "category" in data and data["category"] is not None:
        cat = data.pop("category")
        cat = cat.strip().upper()
        if cat not in BUSINESS_CATEGORIES:
            raise AppValidationError(f"category must be one of {list(BUSINESS_CATEGORIES)}")
        business.category = cat
    if "place_id" in data and data["place_id"] is not None:
        place_id = data.pop("place_id")
        if await db.get(Place, place_id) is None:
            raise NotFoundError("Place not found.")
        business.place_id = place_id
    for field, value in data.items():
        if field == "services" and value is not None:
            value = [s.strip() for s in value if s.strip()]
        setattr(business, field, value)
    if business.status == "REJECTED":
        business.status = "PENDING"
        business.reviewed_by = None
        business.reviewed_at = None
        business.review_note = None
    await db.flush()
    return business


async def list_partners(
    db: AsyncSession, *, category: str | None, city_id: uuid.UUID | None,
    limit: int, offset: int,
) -> tuple[list[BusinessProfile], int]:
    """Local Partners wall (§17): a filtered query over approved, public businesses."""
    stmt = select(BusinessProfile).where(BusinessProfile.status == "APPROVED")
    count_stmt = (
        select(func.count()).select_from(BusinessProfile).where(BusinessProfile.status == "APPROVED")
    )
    if category is not None:
        cat = category.strip().upper()
        if cat not in BUSINESS_CATEGORIES:
            raise AppValidationError(f"category must be one of {list(BUSINESS_CATEGORIES)}")
        stmt = stmt.where(BusinessProfile.category == cat)
        count_stmt = count_stmt.where(BusinessProfile.category == cat)
    if city_id is not None:
        stmt = stmt.where(BusinessProfile.city_id == city_id)
        count_stmt = count_stmt.where(BusinessProfile.city_id == city_id)
    stmt = stmt.order_by(BusinessProfile.created_at.desc()).limit(limit).offset(offset)
    rows = list((await db.scalars(stmt)).all())
    total = (await db.scalar(count_stmt)) or 0
    return rows, total


async def get_public_partner(db: AsyncSession, *, business_id: uuid.UUID) -> BusinessProfile:
    business = await db.get(BusinessProfile, business_id)
    if (
        business is None
        or business.status != "APPROVED"
        or business.visibility != "PUBLIC"
    ):
        raise NotFoundError("Business not found.")
    return business


# ---------- Admin verification queue (§5, §31, §32) ----------

GUIDE_ACTIONS = {"APPROVED": "APPROVE_GUIDE", "REJECTED": "REJECT_GUIDE",
                 "SUSPENDED": "SUSPEND_GUIDE", "PENDING": "REINSTATE_GUIDE"}
BUSINESS_ACTIONS = {"APPROVED": "APPROVE_BUSINESS", "REJECTED": "REJECT_BUSINESS",
                    "SUSPENDED": "SUSPEND_BUSINESS", "PENDING": "REINSTATE_BUSINESS"}


async def admin_list_providers(
    db: AsyncSession, *, kind: str | None, status: str | None
) -> list[dict]:
    """Unified verification queue across guides and businesses, newest first."""
    out: list[dict] = []

    if kind in (None, "GUIDE"):
        stmt = select(GuideProfile)
        if status:
            stmt = stmt.where(GuideProfile.status == status)
        for g in (await db.scalars(stmt.order_by(GuideProfile.created_at.desc()))).all():
            owner = await db.get(User, g.user_id)
            out.append(await _queue_row(db, kind="GUIDE", row=g, owner=owner))
    if kind in (None, "BUSINESS"):
        stmt = select(BusinessProfile)
        if status:
            stmt = stmt.where(BusinessProfile.status == status)
        for b in (await db.scalars(stmt.order_by(BusinessProfile.created_at.desc()))).all():
            owner = await db.get(User, b.user_id)
            out.append(await _queue_row(db, kind="BUSINESS", row=b, owner=owner))
    return out


async def _queue_row(db: AsyncSession, *, kind: str, row, owner: User | None) -> dict:
    from app.modules.providers.identity_service import is_identity_verified

    return {
        "kind": kind,
        "id": row.id,
        "user_id": row.user_id,
        "owner_email": owner.email if owner else None,
        "owner_identity_verified": await is_identity_verified(db, user_id=row.user_id),
        "name": row.public_name if kind == "GUIDE" else row.name,
        "category": None if kind == "GUIDE" else row.category,
        "city_id": row.city_id,
        "status": row.status,
        "visibility": row.visibility,
        "reviewed_at": row.reviewed_at,
        "review_note": row.review_note,
        "created_at": row.created_at,
    }


async def admin_review_provider(
    db: AsyncSession, *, admin: User, kind: str, provider_id: uuid.UUID,
    decision: str, note: str | None,
) -> dict:
    kind = kind.upper()
    decision = decision.strip().upper()
    if decision not in ("APPROVED", "REJECTED", "SUSPENDED", "PENDING", "REINSTATE"):
        raise AppValidationError(
            "decision must be APPROVED, REJECTED, SUSPENDED, PENDING or REINSTATE"
        )

    if kind == "GUIDE":
        row = await db.get(GuideProfile, provider_id)
        actions = GUIDE_ACTIONS
        target_type = "guide_profile"
    elif kind == "BUSINESS":
        row = await db.get(BusinessProfile, provider_id)
        actions = BUSINESS_ACTIONS
        target_type = "business_profile"
    else:
        raise AppValidationError("kind must be GUIDE or BUSINESS")

    if row is None:
        raise NotFoundError(f"{kind.title()} profile not found.")

    before = {"status": row.status}
    # REINSTATE is a suspended → approved transition (schema §5); it is stored
    # as APPROVED but audited under its own action.
    new_status = "APPROVED" if decision == "REINSTATE" else decision
    row.status = new_status
    row.reviewed_by = admin.id
    row.reviewed_at = _now()
    row.review_note = note
    if new_status == "APPROVED":
        row.visibility = "PUBLIC"
    elif new_status in ("REJECTED", "SUSPENDED"):
        row.visibility = "PRIVATE"

    # The actions table maps "PENDING" to the reinstate action by design.
    audit_action = actions["PENDING"] if decision == "REINSTATE" else actions[decision]
    await _audit(
        db, admin=admin, action=audit_action, target_type=target_type,
        target_id=row.id, before=before,
        after={"status": new_status, "visibility": row.visibility},
        note=note,
    )
    await db.flush()
    owner = await db.get(User, row.user_id)
    return await _queue_row(db, kind=kind, row=row, owner=owner)
