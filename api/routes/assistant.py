# api/routes/assistant.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from auth import current_user
from database import db
from schemas import ChatInput
from services import assistant

router = APIRouter(prefix="/assistant", tags=["Copilote IA"])


@router.get("/status")
def status():
    return {"available": assistant.available(), "model": assistant.MODEL if assistant.available() else None}


@router.get("/usage")
async def usage(user: dict = Depends(current_user)):
    """Consommation du copilote par mois (jetons d'entrée / de sortie, nombre de requêtes)."""
    full = await db().get_user_by_email(user["email"])
    return {"limit_per_hour": assistant.RATE_LIMIT, "by_month": (full or {}).get("assistant_usage", {})}


@router.post("/chat")
async def chat(body: ChatInput, user: dict = Depends(current_user)):
    """Réponse du copilote : événements NDJSON diffusés au fil de l'eau (voir services/assistant.py)."""
    if not assistant.available():
        raise HTTPException(503, "Copilote IA non configuré : définir ANTHROPIC_API_KEY dans api/.env")
    if not await assistant.limiter.allow(user["_id"]):
        raise HTTPException(429, f"Limite atteinte ({assistant.RATE_LIMIT} messages par heure). Réessayez plus tard.")
    messages = [m.model_dump() for m in body.messages]
    return StreamingResponse(
        assistant.stream_reply(messages, body.context, user["_id"]),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
