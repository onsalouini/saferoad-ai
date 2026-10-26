# api/routes/reports.py
"""Signalements communautaires : dangers signalés par les utilisateurs, visibles par tous sur la carte."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import current_user
from database import db, new_id
from schemas import ReportInput, ReportVote
from services.shared import RateLimiter

router = APIRouter(prefix="/reports", tags=["Signalements"])

# Durée de vie selon le type : un accident est vite dégagé, un nid-de-poule reste
REPORT_TYPES = {
    "accident": ("Accident", timedelta(hours=3)),
    "bouchon": ("Bouchon", timedelta(hours=2)),
    "travaux": ("Travaux", timedelta(days=7)),
    "nid_de_poule": ("Nid-de-poule", timedelta(days=30)),
    "verglas": ("Verglas / chaussée glissante", timedelta(hours=12)),
    "inondation": ("Inondation", timedelta(hours=24)),
    "obstacle": ("Obstacle sur la route", timedelta(hours=6)),
    "animal": ("Animal sur la route", timedelta(hours=2)),
    "visibilite": ("Visibilité réduite", timedelta(hours=6)),
}
MAX_DENIALS = 3  # au-delà, le signalement disparaît
limiter = RateLimiter("reports", 20, 3600)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _public(r: dict, user_id: str | None = None) -> dict:
    out = {k: v for k, v in r.items() if k not in ("voters", "user_id")}
    out["label"] = REPORT_TYPES.get(r["type"], (r["type"],))[0]
    out["mine"] = bool(user_id and r.get("user_id") == user_id)
    out["voted"] = bool(user_id and user_id in (r.get("voters") or []))
    return out


@router.get("/types")
def types():
    return [{"type": k, "label": v[0], "hours": int(v[1].total_seconds() // 3600)} for k, v in REPORT_TYPES.items()]


@router.get("")
async def list_reports(south: float = Query(..., ge=-90, le=90), west: float = Query(..., ge=-180, le=180),
                       north: float = Query(..., ge=-90, le=90), east: float = Query(..., ge=-180, le=180)):
    if north - south > 5 or east - west > 5:
        raise HTTPException(422, "Zone trop grande (5° au maximum)")
    found = await db().list_reports((south, west, north, east), _now().isoformat(timespec="seconds"))
    return [_public(r) for r in found]


@router.post("", status_code=201)
async def add_report(body: ReportInput, user: dict = Depends(current_user)):
    if body.type not in REPORT_TYPES:
        raise HTTPException(422, f"Type inconnu. Valeurs possibles : {', '.join(REPORT_TYPES)}")
    if not await limiter.allow(user["_id"]):
        raise HTTPException(429, "Trop de signalements en une heure.")
    now = _now()
    doc = {
        "id": new_id(), "user_id": user["_id"], "type": body.type, "comment": (body.comment or "").strip() or None,
        "lat": body.lat, "lng": body.lng,
        "created_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + REPORT_TYPES[body.type][1]).isoformat(timespec="seconds"),
        "confirmations": 0, "denials": 0, "voters": [user["_id"]],
    }
    await db().add_report(doc)
    return _public(doc, user["_id"])


@router.post("/{report_id}/vote")
async def vote(report_id: str, body: ReportVote, user: dict = Depends(current_user)):
    """« Toujours là » prolonge le signalement ; trois « n'est plus là » le retirent."""
    r = await db().get_report(report_id)
    if r is None or r["expires_at"] <= _now().isoformat(timespec="seconds"):
        raise HTTPException(404, "Signalement introuvable ou expiré")
    if user["_id"] in (r.get("voters") or []):
        raise HTTPException(409, "Vous avez déjà donné votre avis sur ce signalement")
    fields = {"voters": (r.get("voters") or []) + [user["_id"]]}
    if body.still_there:
        fields["confirmations"] = r.get("confirmations", 0) + 1
        extended = _now() + REPORT_TYPES.get(r["type"], ("", timedelta(hours=2)))[1] / 2
        fields["expires_at"] = max(r["expires_at"], extended.isoformat(timespec="seconds"))
    else:
        fields["denials"] = r.get("denials", 0) + 1
        if fields["denials"] >= MAX_DENIALS:
            fields["expires_at"] = _now().isoformat(timespec="seconds")
    await db().update_report(report_id, fields)
    return _public({**r, **fields}, user["_id"])
