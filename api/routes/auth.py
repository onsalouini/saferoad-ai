# api/routes/auth.py
from __future__ import annotations

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from auth import clear_session, client_ip, create_token, current_user, hash_password, set_session, verify_password
from database import DuplicateEmail, db
from schemas import ForgotInput, LoginInput, RegisterInput, ResetInput
from services import mailer
from services.shared import RateLimiter

router = APIRouter(prefix="/auth", tags=["Authentification"])

OPTIONAL_FIELDS = ("phone", "location", "gender", "date_of_birth")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
RESET_TTL = timedelta(minutes=30)

# 10 échecs / 15 min par adresse IP, 5 échecs / 15 min par e-mail ; 3 demandes de réinitialisation / heure
login_by_ip = RateLimiter("login-ip", 10, 15 * 60)
login_by_email = RateLimiter("login-email", 5, 15 * 60)
forgot_limiter = RateLimiter("forgot", 3, 3600)


def _public(user: dict) -> dict:
    out = {
        "id": str(user["_id"]),
        "name": user.get("full_name") or user.get("name") or user.get("email"),
        "email": user["email"],
        "created_at": str(user.get("created_at", "")),
        "email_verified": bool(user.get("email_verified")),
    }
    out.update({k: user[k] for k in OPTIONAL_FIELDS if user.get(k)})
    return out


def _session(response: Response, user: dict) -> dict:
    token = create_token(user["_id"])
    set_session(response, token)
    # Le jeton reste renvoyé pour les clients API (le frontend web utilise le cookie)
    return {"token": token, "user": _public(user)}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/register", status_code=201)
async def register(body: RegisterInput, response: Response):
    email = body.email.lower()
    if await db().get_user_by_email(email):
        raise HTTPException(409, "Un compte existe déjà avec cet e-mail")
    user = {
        "full_name": body.name.strip(),
        "email": email,
        "password_hash": hash_password(body.password),
        **{k: getattr(body, k) for k in OPTIONAL_FIELDS if getattr(body, k)},
        "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    }
    try:
        user["_id"] = await db().create_user(user)
    except DuplicateEmail:
        raise HTTPException(409, "Un compte existe déjà avec cet e-mail")
    from routes.account import send_verification

    await send_verification(user, FRONTEND_URL)
    return _session(response, user)


@router.post("/login")
async def login(body: LoginInput, request: Request, response: Response):
    email, ip = body.email.lower(), client_ip(request)
    if await login_by_ip.blocked(ip) or await login_by_email.blocked(email):
        raise HTTPException(429, "Trop de tentatives. Réessayez dans 15 minutes ou réinitialisez votre mot de passe.")
    user = await db().get_user_by_email(email)
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        await login_by_ip.hit(ip)
        await login_by_email.hit(email)
        raise HTTPException(401, "E-mail ou mot de passe incorrect")
    await login_by_email.reset(email)
    return _session(response, user)


@router.post("/logout", status_code=204)
async def logout(response: Response):
    clear_session(response)


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return _public(user)


@router.post("/forgot", status_code=202)
async def forgot(body: ForgotInput, request: Request):
    """Envoie un lien de réinitialisation. Réponse identique que le compte existe ou non."""
    email, ip = body.email.lower(), client_ip(request)
    done = {"message": "Si un compte existe pour cet e-mail, un lien de réinitialisation vient d'être envoyé."}
    if await forgot_limiter.blocked(ip) or await forgot_limiter.blocked(email):
        return done
    await forgot_limiter.hit(ip)
    await forgot_limiter.hit(email)
    user = await db().get_user_by_email(email)
    if user:
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + RESET_TTL).isoformat(timespec="seconds")
        await db().update_user(user["_id"], {"reset_token_hash": _hash_token(token), "reset_expires": expires})
        link = f"{FRONTEND_URL}/reinitialiser?token={token}"
        await mailer.send(email, "SafeRoad AI : réinitialisation de votre mot de passe", (
            f"Bonjour {user.get('full_name') or ''},\n\n"
            f"Pour choisir un nouveau mot de passe, ouvrez ce lien (valable 30 minutes) :\n{link}\n\n"
            "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail.\n\nSafeRoad AI"))
    return done


@router.post("/reset")
async def reset(body: ResetInput, response: Response):
    user = await db().get_user_by_field("reset_token_hash", _hash_token(body.token))
    if not user or datetime.fromisoformat(user.get("reset_expires", "1970-01-01T00:00:00+00:00")) < datetime.now(timezone.utc):
        raise HTTPException(400, "Lien invalide ou expiré. Refaites une demande.")
    await db().update_user(user["_id"], {
        "password_hash": hash_password(body.password),
        "password_changed_at": int(time.time()),  # invalide les sessions ouvertes avant
        "reset_token_hash": None, "reset_expires": None,
    })
    await login_by_email.reset(user["email"])
    return _session(response, user)
