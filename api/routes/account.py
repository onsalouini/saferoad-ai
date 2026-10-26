# api/routes/account.py
"""Compte : vérification de l'e-mail, notifications push, export et suppression des données (RGPD)."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse

from auth import clear_session, current_user, verify_password
from database import db, new_id
from schemas import DeleteAccountInput, PushSubscriptionInput, VerifyInput
from services import mailer, push
from services.shared import RateLimiter

router = APIRouter(tags=["Compte"])
verify_limiter = RateLimiter("verify", 3, 3600)
PRIVATE_FIELDS = ("password_hash", "reset_token_hash", "reset_expires", "verify_token_hash")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def send_verification(user: dict, frontend_url: str) -> None:
    token = secrets.token_urlsafe(32)
    await db().update_user(user["_id"], {"verify_token_hash": _hash(token)})
    await mailer.send(user["email"], "SafeRoad AI : confirmez votre adresse e-mail", (
        f"Bonjour {user.get('full_name') or ''},\n\n"
        f"Confirmez votre adresse pour recevoir les alertes de départ par e-mail :\n"
        f"{frontend_url}/verifier-email?token={token}\n\nSafeRoad AI"))


@router.post("/auth/verify/send", status_code=202)
async def resend_verification(user: dict = Depends(current_user)):
    from routes.auth import FRONTEND_URL

    if user.get("email_verified"):
        return {"message": "Adresse déjà confirmée."}
    if not await verify_limiter.allow(user["_id"]):
        raise HTTPException(429, "Trop de demandes, réessayez dans une heure.")
    await send_verification(user, FRONTEND_URL)
    return {"message": "E-mail de confirmation envoyé."}


@router.post("/auth/verify")
async def verify_email(body: VerifyInput):
    user = await db().get_user_by_field("verify_token_hash", _hash(body.token))
    if user is None:
        raise HTTPException(400, "Lien invalide ou déjà utilisé.")
    await db().update_user(user["_id"], {"email_verified": True, "verify_token_hash": None})
    return {"message": "Adresse e-mail confirmée."}


# ------------------------------------------------------------------- push
@router.get("/push/public-key")
def push_key():
    key = push.public_key()
    if key is None:
        raise HTTPException(503, "Notifications push indisponibles sur ce serveur")
    return {"public_key": key}


@router.post("/push/subscribe", status_code=201)
async def subscribe(body: PushSubscriptionInput, user: dict = Depends(current_user)):
    existing = await db().list_items(user["_id"], "push_subscriptions")
    for s in existing:
        if s["endpoint"] == body.endpoint:
            return {"id": s["id"]}
    sub = {"id": new_id(), "endpoint": body.endpoint, "keys": body.keys.model_dump(),
           "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    await db().push_item(user["_id"], "push_subscriptions", sub)
    return {"id": sub["id"]}


@router.post("/push/test")
async def push_test(user: dict = Depends(current_user)):
    sent = await push.notify(user, "SafeRoad AI", "Les notifications fonctionnent sur cet appareil.")
    return {"sent": sent}


@router.delete("/push/subscribe", status_code=204)
async def unsubscribe(endpoint: str, user: dict = Depends(current_user)):
    for s in await db().list_items(user["_id"], "push_subscriptions"):
        if s["endpoint"] == endpoint:
            await db().pull_item(user["_id"], "push_subscriptions", s["id"])


# ------------------------------------------------------------------- RGPD
@router.get("/account/export")
async def export(user: dict = Depends(current_user)):
    """Toutes les données du compte, en JSON téléchargeable (droit d'accès et de portabilité)."""
    full = await db().get_user_by_email(user["email"]) or {}
    data = {k: v for k, v in full.items() if k not in PRIVATE_FIELDS}
    for field in ("history", "saved_trips", "notifications"):
        data[field] = await db().list_items(user["_id"], field)
    data["push_subscriptions"] = len(await db().list_items(user["_id"], "push_subscriptions"))
    data["exported_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return JSONResponse(data, headers={"Content-Disposition": 'attachment; filename="saferoad-mes-donnees.json"'})


@router.post("/account/delete", status_code=204)
async def delete_account(body: DeleteAccountInput, response: Response, user: dict = Depends(current_user)):
    """Suppression définitive du compte (droit à l'effacement). Les signalements publiés restent, anonymisés."""
    full = await db().get_user_by_email(user["email"]) or {}
    if not verify_password(body.password, full.get("password_hash", "")):
        raise HTTPException(403, "Mot de passe incorrect")
    await db().delete_user(user["_id"])
    clear_session(response)
