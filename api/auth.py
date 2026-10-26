# api/auth.py
"""
Hachage des mots de passe (bcrypt) et jetons JWT (limitation des tentatives : services/shared.py).

Le jeton est posé dans un cookie httpOnly (inaccessible au JavaScript, donc à l'abri d'une faille XSS).
L'en-tête « Authorization: Bearer » reste accepté pour les clients API.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database import db

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # Secret éphémère : les sessions sont perdues au redémarrage. Définir JWT_SECRET dans .env.
    JWT_SECRET = secrets.token_urlsafe(32)
    print("ATTENTION : JWT_SECRET absent du .env, secret temporaire genere")
JWT_ALGO = "HS256"
JWT_TTL = timedelta(days=7)

COOKIE_NAME = "saferoad_session"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"  # true en production (HTTPS)
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")  # "none" si le frontend est sur un autre domaine

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    # Un hachage invalide (ex. données d'exemple "$2b$12$hashed_password_example") -> refus, pas d'erreur 500
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user_id, "iat": now, "exp": now + JWT_TTL}, JWT_SECRET, algorithm=JWT_ALGO)


def set_session(response: Response, token: str) -> None:
    response.set_cookie(COOKIE_NAME, token, max_age=int(JWT_TTL.total_seconds()), httponly=True,
                        secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, path="/")


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)


async def _user_from(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session invalide ou expirée")
    user = await db().get_user(payload["sub"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Utilisateur introuvable")
    # Jeton émis avant un changement de mot de passe -> refusé
    changed = user.get("password_changed_at")
    if changed and payload.get("iat", 0) < changed:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expirée, reconnectez-vous")
    return user


def _token(request: Request, creds: HTTPAuthorizationCredentials | None) -> str | None:
    return creds.credentials if creds else request.cookies.get(COOKIE_NAME)


async def current_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    user = await _user_from(_token(request, creds))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise")
    return user


async def optional_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict | None:
    try:
        return await _user_from(_token(request, creds))
    except HTTPException:
        return None  # session expirée : l'analyse reste possible, sans historique


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "inconnu"
