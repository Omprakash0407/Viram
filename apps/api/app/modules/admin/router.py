"""Admin + community endpoints: public suggestion intake, admin moderation, audit log."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.commerce import AdminAuditLog
from app.models.user import User
from app.modules.admin import service
from app.modules.admin.schemas import (
    SuggestionCreate,
    SuggestionList,
    SuggestionOut,
    SuggestionReview,
)
from app.modules.users.deps import require_admin

router = APIRouter(tags=["community", "admin"])


@router.post("/community/suggestions", response_model=SuggestionOut, status_code=201)
async def submit_suggestion(
    payload: SuggestionCreate,
    db: AsyncSession = Depends(get_db),
) -> SuggestionOut:
    """Public intake for local knowledge. Lands PENDING — never auto-published (§14)."""
    suggestion = await service.create_suggestion(db, payload=payload)
    await db.commit()
    return suggestion


@router.get("/admin/suggestions", response_model=SuggestionList)
async def admin_list_suggestions(
    status: str | None = Query(default=None, pattern="^(PENDING|APPROVED|REJECTED)$"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SuggestionList:
    items = await service.list_suggestions(db, admin=admin, status=status)
    return SuggestionList(items=items)


@router.post("/admin/suggestions/{suggestion_id}/review", response_model=SuggestionOut)
async def admin_review_suggestion(
    suggestion_id: uuid.UUID,
    payload: SuggestionReview,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SuggestionOut:
    """Approve/reject with note — audited (§32)."""
    suggestion = await service.review_suggestion(
        db, admin=admin, suggestion_id=suggestion_id,
        decision=payload.decision, note=payload.admin_note,
    )
    await db.commit()
    return suggestion


@router.get("/admin/audit-log")
async def admin_audit_log(
    limit: int = Query(default=100, ge=1, le=500),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Append-only audit trail, newest first (admin-only visibility, §30)."""
    rows = (
        await db.scalars(
            select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(limit)
        )
    ).all()
    return {
        "items": [
            {
                "id": str(r.id),
                "admin_id": str(r.admin_id),
                "action": r.action,
                "target_type": r.target_type,
                "target_id": str(r.target_id),
                "before": r.before,
                "after": r.after,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }
