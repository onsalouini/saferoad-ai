# api/auth.py
"""Hachage des mots de passe (bcrypt) et jetons JWT."""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database import db

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # Secret éphémère : les sessions sont perdues au redémarrage. Définir JWT_SECRET dans .env.
    JWT_SECRET = secrets.token_urlsafe(32)
    print("ATTENTION : JWT_SECRET absent du .env, secret temporaire genere")
JWT_ALGO = "HS256"
JWT_TTL = timedelta(days=7)

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user_id, "iat": now, "exp": now + JWT_TTL}, JWT_SECRET, algorithm=JWT_ALGO)


async def _user_from(creds: HTTPAuthorizationCredentials | None) -> dict | None:
    if creds is None:
        return None
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session invalide ou expirée")
    user = await db().find_one("users", {"_id": payload["sub"]})
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Utilisateur introuvable")
    return user


async def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    user = await _user_from(creds)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise")
    return user


async def optional_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict | None:
    return await _user_from(creds)
