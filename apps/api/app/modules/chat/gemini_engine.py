"""Vira AI (beta) — Gemini function-calling engine.

The model NEVER touches the database directly. It proposes tool calls; every
tool executes the same guarded service functions the REST API uses (ownership,
validation, audit). If Gemini is unconfigured or fails, the caller falls back
to the rule-based Vira — never fake output.

Model contract (system prompt): answers must be grounded in the provided
verified destination data + the user's own history; if the data doesn't
contain the answer, say so honestly (design rule 8: nothing is invented).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.chat import retrieval

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

MAX_TOOL_ROUNDS = 3

SYSTEM_PROMPT = """You are Vira, the AI trip assistant for VIRAM, a tourism platform \
currently live for Odisha, India.

HARD RULES (violating any of these is a defect):
1. Ground every factual claim in the VERIFIED DATA and MY DATA sections of this \
prompt. If the answer is not there, say "I don't have verified information on \
that" and offer what you do have. NEVER invent places, facts, fees or customs.
2. Odisha is the only state with verified content. For other Indian states, say \
content is coming soon and suggest Odisha.
3. To plan or change a trip you MUST call tools — never claim you did something \
without the corresponding tool call succeeding.
4. Be warm and concise (under 120 words unless listing an itinerary). Use simple \
markdown-free text; the UI renders plain text.

TOOL NOTES:
- suggest_trip creates a full trip + itinerary in one call; the user must be signed in.
- city must be a VERIFIED DATA city name (e.g. "Puri", "Bhubaneswar", "Konark"). \
Dates are ISO YYYY-MM-DD.
"""


def _tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "name": "suggest_trip",
            "description": "Create a complete trip with recommendations and a day-by-day itinerary for the signed-in user.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "city": {"type": "STRING", "description": "City name from VERIFIED DATA, e.g. Puri"},
                    "start_date": {"type": "STRING", "description": "ISO date YYYY-MM-DD"},
                    "end_date": {"type": "STRING", "description": "ISO date YYYY-MM-DD"},
                    "party_size": {"type": "INTEGER", "description": "Number of travellers, 1-50"},
                    "moods": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "Subset of: NATURE_RELAXATION, CITY_LIFE, ADVENTURE_THRILL, FOOD_CULTURE",
                    },
                    "budget_tier": {
                        "type": "STRING",
                        "description": "One of: BUDGET, MODERATE, PREMIUM, EXECUTIVE",
                    },
                },
                "required": ["city", "start_date", "end_date", "moods", "budget_tier"],
            },
        },
        {
            "name": "get_weather",
            "description": "Weather forecast snapshot for a VERIFIED city (optional ISO date).",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "city": {"type": "STRING"},
                    "date": {"type": "STRING", "description": "ISO date, optional"},
                },
                "required": ["city"],
            },
        },
        {
            "name": "list_my_trips",
            "description": "List the signed-in user's recent trips with itinerary summaries.",
            "parameters": {"type": "OBJECT", "properties": {}},
        },
    ]


def _compact_places(brief: dict) -> str:
    lines = []
    for p in brief["places"]:
        bits = [f"- {p['name']} ({p['category']}, {p['classification']}"]
        if p.get("rating") is not None:
            bits.append(f"rating {p['rating']}")
        bits.append(f"~{p.get('visit_minutes') or 60} min)")
        line = " ".join(bits)
        if p.get("description"):
            line += f": {p['description']}"
        for key in ("best_time", "entry_fee"):
            if p.get(key):
                line += f" | {key.replace('_', ' ')}: {p[key]}"
        lines.append(line)
    return "\n".join(lines)


def _compact_user(uctx: dict) -> str:
    parts = []
    if uctx.get("interests"):
        parts.append(f"Interests: {', '.join(uctx['interests'])}")
    if uctx.get("budget_level"):
        parts.append(f"Saved budget level: {uctx['budget_level']}")
    for t in uctx.get("recent_trips", [])[:4]:
        parts.append(
            f"Trip: {t['city']} {t['dates']} ({t['status']}, {t['party_size']} travellers, "
            f"moods {','.join(t['moods']) or 'n/a'})"
            + (f" — visited {', '.join(t['visited_places'][:5])}" if t["visited_places"] else "")
        )
    return "\n".join(parts) if parts else "No previous trips — this would be their first."


class GeminiChatEngine:
    """One conversational turn: grounding context in → text and/or tool loop → answer."""

    ENGINE_NAME = "GeminiChatEngine"
    ENGINE_VERSION = "gemini-beta-v1"

    def __init__(self) -> None:
        self._api_key = settings.GEMINI_API_KEY
        self._model = settings.GEMINI_MODEL

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def generate(
        self,
        db: AsyncSession,
        *,
        user: Any,
        user_text: str,
        history: list[dict[str, str]] | None = None,
        tool_executor: Any = None,
    ) -> dict[str, Any]:
        """Run one turn. Returns {reply, tool_calls, trip_id?}.

        tool_executor: async (name, args, db, user) -> dict — injected by the
        router so the engine stays free of service-layer imports (and the
        router can audit what the model did).
        """
        if not self.configured:
            raise RuntimeError("GeminiChatEngine is not configured")
        if tool_executor is None:
            raise ValueError("tool_executor is required")

        # --- grounding context --------------------------------------------------
        mentioned_city = await retrieval.resolve_city(db, name=user_text)
        brief = (
            await retrieval.destination_brief(db, city_id=mentioned_city.id)
            if mentioned_city
            else None
        )
        uctx = await retrieval.user_context(db, user_id=user.id)

        context_lines = []
        if brief:
            context_lines.append(
                f"VERIFIED DATA for {brief['city']}, {brief['state']}:\n{_compact_places(brief)}"
            )
        else:
            context_lines.append(
                "VERIFIED DATA: the user has not mentioned a specific city. "
                "VIRAM currently has verified content for cities across Odisha "
                "(Puri, Bhubaneswar, Konark, Chilika-Satapada, Daringbadi and more)."
            )
        context_lines.append(f"MY DATA (this traveller's own history):\n{_compact_user(uctx)}")

        # --- payload --------------------------------------------------------------
        contents: list[dict[str, Any]] = []
        for m in (history or [])[-8:]:
            role = "user" if m.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.get("text", "")}]})
        contents.append(
            {
                "role": "user",
                "parts": [
                    {"text": "\n\n".join(context_lines)},
                    {"text": f"USER MESSAGE: {user_text}"},
                ],
            }
        )

        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents,
            "tools": [{"function_declarations": _tool_schemas()}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 700,
                # 3.6-flash is a thinking model: thought tokens share the
                # output budget and truncated answers mid-sentence. Chat
                # grounding needs no deliberation — disable it.
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }

        # --- tool loop ---------------------------------------------------------
        tool_calls: list[dict[str, Any]] = []
        trip_id: str | None = None
        url = API_URL.format(model=self._model)
        async with httpx.AsyncClient(timeout=30) as client:
            for _round in range(MAX_TOOL_ROUNDS):
                # Free-tier Gemini intermittently answers 503/429 under load;
                # one short retry absorbs the common transient blip before we
                # surface an honest failure to the user.
                res: httpx.Response | None = None
                for attempt in range(2):
                    res = await client.post(
                        url,
                        params={"key": self._api_key},
                        json=payload,
                    )
                    if res.status_code in (429, 503) and attempt == 0:
                        await asyncio.sleep(1.5)
                        continue
                    break
                assert res is not None
                if res.status_code == 429:
                    raise RuntimeError("Gemini rate limit (429)")
                res.raise_for_status()
                data = res.json()
                cand = (data.get("candidates") or [{}])[0]
                parts = ((cand.get("content") or {}).get("parts")) or []
                fn_parts = [p["functionCall"] for p in parts if "functionCall" in p]
                if not fn_parts:
                    reply = " ".join(p.get("text", "") for p in parts).strip()
                    return {"reply": reply or "I'm here — ask me about Odisha trips.", "tool_calls": tool_calls, "trip_id": trip_id}
                # execute every proposed call, feed results back
                contents.append({"role": "model", "parts": parts})
                result_parts = []
                for call in fn_parts:
                    name = call.get("name", "")
                    args = call.get("args", {}) or {}
                    try:
                        result = await tool_executor(name, args, db, user)
                    except Exception as exc:  # noqa: BLE001 — surfaced to the model, then user
                        result = {"error": str(exc)[:200]}
                    tool_calls.append({"name": name, "args": args, "ok": "error" not in result})
                    if name == "suggest_trip" and result.get("trip_id"):
                        trip_id = result["trip_id"]
                    result_parts.append(
                        {"functionResponse": {"name": name, "response": _small(result)}}
                    )
                contents.append({"role": "user", "parts": result_parts})
                payload["contents"] = contents

        # loop exhausted without final text — summarize what happened
        if trip_id:
            return {
                "reply": "Your trip is ready — open it from My Trips to see the full itinerary.",
                "tool_calls": tool_calls,
                "trip_id": trip_id,
            }
        return {
            "reply": "I ran into trouble completing that. Please try rephrasing.",
            "tool_calls": tool_calls,
            "trip_id": None,
        }


def _small(result: dict[str, Any], limit: int = 1800) -> dict[str, Any]:
    """Trim tool results so function responses stay small and cheap."""
    out: dict[str, Any] = {}
    size = 0
    for k, v in result.items():
        piece = str(v)
        if size + len(piece) > limit:
            out[k] = piece[: max(0, limit - size)]
            break
        out[k] = v
        size += len(piece)
    return out


async def probe_model(db: AsyncSession) -> list[dict[str, Any]]:
    """Small helper used by tests/admin: list active cities (sanity check)."""
    from app.models.geo import City

    rows = (await db.scalars(select(City).limit(10))).all()
    return [{"id": str(c.id), "name": c.name} for c in rows]
