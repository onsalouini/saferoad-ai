# api/routes/auth.py
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import create_token, current_user, hash_password, verify_password
from database import db
from schemas import LoginInput, RegisterInput

router = APIRouter(prefix="/auth", tags=["Authentification"])


def _public(user: dict) -> dict:
    return {"id": user["_id"], "name": user["name"], "email": user["email"], "created_at": user["created_at"]}


@router.post("/register", status_code=201)
async def register(body: RegisterInput):
    email = body.email.lower()
    if await db().find_one("users", {"email": email}):
        raise HTTPException(409, "Un compte existe déjà avec cet e-mail")
    user = {
        "name": body.name.strip(), "email": email, "password": hash_password(body.password),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    user["_id"] = await db().insert("users", user)
    return {"token": create_token(user["_id"]), "user": _public(user)}


@router.post("/login")
async def login(body: LoginInput):
    user = await db().find_one("users", {"email": body.email.lower()})
    if not user or not verify_password(body.password, user["password"]):
        raise HTTPException(401, "E-mail ou mot de passe incorrect")
    return {"token": create_token(user["_id"]), "user": _public(user)}


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return _public(user)
