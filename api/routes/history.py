# api/routes/history.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import current_user
from database import db

router = APIRouter(prefix="/history", tags=["Historique"])


@router.get("")
async def list_history(limit: int = Query(50, ge=1, le=200), user: dict = Depends(current_user)):
    return await db().list_items(user["_id"], "history", limit)


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: str, user: dict = Depends(current_user)):
    if not await db().pull_item(user["_id"], "history", item_id):
        raise HTTPException(404, "Élément introuvable")


@router.delete("", status_code=204)
async def clear_history(user: dict = Depends(current_user)):
    await db().clear_items(user["_id"], "history")
