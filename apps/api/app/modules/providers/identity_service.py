"""Identity verification service — persistence half of the verifier flow.

Endpoint rule (§2): users act only on their OWN verification rows. The
complete step is reachable only by the row's owner while it is PENDING; the
verifier implementation is the single place that decides the outcome.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.exceptions import ValidationError as AppValidationError
from app.models.providers import IdentityVerification
from app.models.user import User
from app.modules.providers.identity import get_identity_verifier


async def is_identity_verified(db: AsyncSession, *, user_id: uuid.UUID) -> bool:
    """Derived flag: latest APPROVED, non-expired verification for the user."""
    row = await db.scalar(
        select(IdentityVerification)
        .where(
            IdentityVerification.user_id == user_id,
            IdentityVerification.status == "APPROVED",
        )
        .order_by(IdentityVerification.requested_at.desc())
        .limit(1)
    )
    if row is None:
        return False
    if row.expires_at is not None:
        if row.expires_at < datetime.now(timezone.utc):
            return False
    return True


async def init_verification(
    db: AsyncSession, *, user: User, id_proof_type: str
) -> tuple[IdentityVerification, str, str]:
    id_proof_type = id_proof_type.strip().upper()
    if id_proof_type not in ("AADHAAR", "DRIVING_LICENCE", "VOTER_ID", "PASSPORT"):
        raise AppValidationError("Unsupported id proof type.")

    verifier = get_identity_verifier()
    consent_url, note = await verifier.initiate(user_id=user.id, id_proof_type=id_proof_type)
    row = IdentityVerification(
        user_id=user.id,
        provider=verifier.name,
        id_proof_type=id_proof_type,
        status="PENDING",
    )
    db.add(row)
    await db.flush()
    return row, consent_url, note


async def complete_verification(
    db: AsyncSession, *, user: User, verification_id: uuid.UUID
) -> tuple[IdentityVerification, str]:
    row = await db.get(IdentityVerification, verification_id)
    if row is None or row.user_id != user.id:
        raise NotFoundError("Verification session not found.")
    if row.status != "PENDING":
        raise AppValidationError("This verification session is already closed.")

    verifier = get_identity_verifier()
    result = await verifier.complete(
        user_id=user.id, verification_id=row.id, id_proof_type=row.id_proof_type
    )
    row.status = "APPROVED" if result.verified else "FAILED"
    row.provider_reference = result.provider_reference
    row.verified_at = datetime.now(timezone.utc) if result.verified else None
    row.expires_at = result.expires_at
    await db.flush()
    return row, result.note


async def my_status(db: AsyncSession, *, user: User) -> tuple[bool, IdentityVerification | None]:
    latest = await db.scalar(
        select(IdentityVerification)
        .where(IdentityVerification.user_id == user.id)
        .order_by(IdentityVerification.requested_at.desc())
        .limit(1)
    )
    return await is_identity_verified(db, user_id=user.id), latest
