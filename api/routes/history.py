# api/routes/history.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import current_user
from database import db

router = APIRouter(prefix="/history", tags=["Historique"])


def _clean(doc: dict) -> dict:
    return {("id" if k == "_id" else k): v for k, v in doc.items() if k != "user_id"}


@router.get("")
async def list_history(limit: int = Query(50, ge=1, le=200), user: dict = Depends(current_user)):
    docs = await db().find("history", {"user_id": user["_id"]}, limit=limit)
    return [_clean(d) for d in docs]


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: str, user: dict = Depends(current_user)):
    if not await db().delete("history", {"_id": item_id, "user_id": user["_id"]}):
        raise HTTPException(404, "Élément introuvable")


@router.delete("", status_code=204)
async def clear_history(user: dict = Depends(current_user)):
    await db().delete("history", {"user_id": user["_id"]})
