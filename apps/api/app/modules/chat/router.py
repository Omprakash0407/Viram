"""Vira AI (beta) endpoint.

Auth required (full-history personalization). Without a configured Gemini key
the endpoint returns an honest 503 — it never fakes AI output. A simple
per-minute rate guard protects the free-tier quota. Every tool call the model
proposes executes the same guarded services the REST API uses; nothing the
model says can bypass ownership or validation.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import ValidationFailedError
from app.models.user import User
from app.modules.chat.gemini_engine import GeminiChatEngine
from app.modules.chat.tools import execute_tool
from app.modules.users.deps import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])

engine = GeminiChatEngine()

# In-process sliding window (single-process MVP; swap for Redis if scaled).
_rate_bucket: dict[str, list[float]] = {}


class HistoryTurn(BaseModel):
    """Tolerant: junk entries are dropped by the validator, not rejected."""

    model_config = ConfigDict(coerce_numbers_to_str=True)

    role: str = "user"
    text: str = ""

    @field_validator("text", mode="before")
    @classmethod
    def _text_to_str(cls, v: object) -> str:
        return str(v) if v is not None else ""


class AiChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[HistoryTurn] = Field(
        default_factory=list,
        description="Optional recent turns",
    )


class AiChatResponse(BaseModel):
    reply: str
    engine: str = "GeminiChatEngine"
    tool_calls: list[dict] = Field(default_factory=list)
    trip_id: str | None = None
    beta: bool = True


@router.post("/ai", response_model=AiChatResponse)
async def ai_chat(
    payload: AiChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiChatResponse:
    if not engine.configured:
        raise ValidationFailedError(
            "Vira AI (beta) is not configured on this server — add a Gemini API "
            "key (GEMINI_API_KEY) to enable it. The classic Vira assistant still works."
        )

    # rate guard
    now = time.monotonic()
    window = _rate_bucket.setdefault(user.id, [])
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= settings.AI_CHAT_RATE_LIMIT_PER_MIN:
        raise ValidationFailedError(
            "You're sending messages too quickly — try again in a moment."
        )
    window.append(now)

    history = [
        {"role": ("user" if h.role == "user" else "bot"), "text": h.text[:1000]}
        for h in payload.history[-8:]
        if h.text
    ]

    try:
        result = await engine.generate(
            db,
            user=user,
            user_text=payload.message,
            history=history,
            tool_executor=execute_tool,
        )
    except Exception as exc:  # noqa: BLE001 — honest failure, no fake answer
        await db.rollback()
        raise ValidationFailedError(
            "Vira AI couldn't answer right now (the AI provider may be busy). "
            "Please try again, or use the classic assistant."
        ) from exc

    # Tool side-effects (trips, itinerary, weather cache) were flushed inside
    # the request session — commit them, or everything rolls back and the bot
    # would claim a trip was saved while the database says otherwise.
    await db.commit()

    return AiChatResponse(
        reply=result["reply"],
        tool_calls=result.get("tool_calls", []),
        trip_id=result.get("trip_id"),
    )
