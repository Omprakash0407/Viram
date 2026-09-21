"""Provider + identity endpoints (design doc §3–§5, §17; Phase 7 addendum).

Public:  Local Partners wall and partner detail — APPROVED+PUBLIC rows only.
Owner:   guide upsert (0..1), business CRUD (0..N), identity verify flow.
Admin:   unified verification queue with audited decisions (§31–§32).
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models.user import User
from app.modules.providers import identity_service, service
from app.modules.providers.schemas import (
    AdminProviderOut,
    BusinessList,
    BusinessProfileCreate,
    BusinessProfileOut,
    BusinessProfileUpdate,
    BusinessPublicOut,
    GuideProfileOut,
    GuideProfileUpsert,
    IdentityInitOut,
    IdentityStatus,
    IdentityVerificationOut,
    ProviderReview,
)
from app.modules.users.deps import get_current_user, require_admin

router = APIRouter(tags=["providers", "identity"])


# ---------- Guide profile (owner) ----------

@router.get("/guides/me", response_model=GuideProfileOut)
async def my_guide_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GuideProfileOut:
    guide = await service.get_or_init_guide(db, user=user)
    if guide is None:
        raise NotFoundError("No guide profile yet — register one first.")
    return guide


@router.put("/guides/me", response_model=GuideProfileOut, status_code=200)
async def upsert_guide_profile(
    payload: GuideProfileUpsert,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GuideProfileOut:
    guide = await service.upsert_guide(db, user=user, payload=payload)
    await db.commit()
    return guide


# ---------- Business profile (owner) ----------

@router.post("/businesses", response_model=BusinessProfileOut, status_code=201)
async def create_business(
    payload: BusinessProfileCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessProfileOut:
    business = await service.create_business(db, user=user, payload=payload)
    await db.commit()
    return business


@router.get("/businesses/mine", response_model=list[BusinessProfileOut])
async def my_businesses(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BusinessProfileOut]:
    return await service.list_my_businesses(db, user=user)


@router.patch("/businesses/{business_id}", response_model=BusinessProfileOut)
async def update_business(
    business_id: uuid.UUID,
    payload: BusinessProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessProfileOut:
    business = await service.update_business(db, user=user, business_id=business_id, payload=payload)
    await db.commit()
    return business


# ---------- Local Partners wall (public, §17) ----------

@router.get("/partners", response_model=BusinessList)
async def list_partners(
    category: str | None = Query(default=None),
    city_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> BusinessList:
    rows, total = await service.list_partners(
        db, category=category, city_id=city_id, limit=limit, offset=offset
    )
    return BusinessList(items=[BusinessPublicOut.model_validate(r) for r in rows], total=total)


@router.get("/partners/{business_id}", response_model=BusinessPublicOut)
async def partner_detail(
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BusinessPublicOut:
    return await service.get_public_partner(db, business_id=business_id)


# ---------- Identity verification (owner, Phase 7 addendum) ----------

@router.post("/identity/verify/init", response_model=IdentityInitOut, status_code=201)
async def identity_verify_init(
    id_proof_type: str = Query(default="AADHAAR"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IdentityInitOut:
    row, consent_url, note = await identity_service.init_verification(
        db, user=user, id_proof_type=id_proof_type
    )
    await db.commit()
    return IdentityInitOut(
        verification=IdentityVerificationOut.model_validate(row),
        consent_url=consent_url,
        demo_note=note,
    )


@router.post("/identity/verify/{verification_id}/complete", response_model=IdentityInitOut)
async def identity_verify_complete(
    verification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IdentityInitOut:
    row, note = await identity_service.complete_verification(
        db, user=user, verification_id=verification_id
    )
    await db.commit()
    verifier_note = note  # carries the honest demo label
    return IdentityInitOut(
        verification=IdentityVerificationOut.model_validate(row),
        consent_url="",
        demo_note=verifier_note,
    )


@router.get("/identity/verify/me", response_model=IdentityStatus)
async def identity_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IdentityStatus:
    verified, latest = await identity_service.my_status(db, user=user)
    return IdentityStatus(
        identity_verified=verified,
        latest=IdentityVerificationOut.model_validate(latest) if latest else None,
        demo_note=(
            "Verification runs on the DEMO DigiLocker verifier — no document "
            "number is ever requested, transmitted or stored by VIRĀM. The real "
            "integration needs DigiLocker API credentials."
        ),
    )


# ---------- Admin verification queue (§5, §31, §32) ----------

@router.get("/admin/providers", response_model=list[AdminProviderOut])
async def admin_list_providers(
    kind: str | None = Query(default=None, pattern="^(GUIDE|BUSINESS)$"),
    status: str | None = Query(
        default=None, pattern="^(PENDING|APPROVED|REJECTED|SUSPENDED)$"
    ),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminProviderOut]:
    rows = await service.admin_list_providers(db, kind=kind, status=status)
    return [AdminProviderOut.model_validate(r) for r in rows]


@router.post("/admin/providers/{kind}/{provider_id}/review", response_model=AdminProviderOut)
async def admin_review_provider(
    kind: str,
    provider_id: uuid.UUID,
    payload: ProviderReview,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminProviderOut:
    row = await service.admin_review_provider(
        db, admin=admin, kind=kind, provider_id=provider_id,
        decision=payload.decision, note=payload.admin_note,
    )
    await db.commit()
    return AdminProviderOut.model_validate(row)
