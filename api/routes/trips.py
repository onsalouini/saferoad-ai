# api/routes/trips.py
"""Trajets enregistrés (alertes de départ) et notifications."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import current_user
from database import LIST_MAX, db, new_id
from schemas import SavedTripInput
from services import mailer, scheduler
from services.trip import TripError

router = APIRouter(tags=["Alertes de départ"])


@router.get("/trips")
async def list_trips(user: dict = Depends(current_user)):
    return await db().list_items(user["_id"], "saved_trips")


@router.post("/trips", status_code=201)
async def add_trip(body: SavedTripInput, user: dict = Depends(current_user)):
    if len(await db().list_items(user["_id"], "saved_trips")) >= LIST_MAX["saved_trips"]:
        raise HTTPException(409, f"Limite de {LIST_MAX['saved_trips']} trajets enregistrés atteinte")
    trip = {"id": new_id(), "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **body.model_dump(), "last_alert_date": None}
    await db().push_item(user["_id"], "saved_trips", trip)
    return trip


@router.delete("/trips/{trip_id}", status_code=204)
async def delete_trip(trip_id: str, user: dict = Depends(current_user)):
    if not await db().pull_item(user["_id"], "saved_trips", trip_id):
        raise HTTPException(404, "Trajet introuvable")


@router.post("/trips/{trip_id}/check")
async def check_now(trip_id: str, user: dict = Depends(current_user)):
    """Lance tout de suite la vérification d'un trajet enregistré (sans attendre l'heure prévue)."""
    trip = next((t for t in await db().list_items(user["_id"], "saved_trips") if t["id"] == trip_id), None)
    if trip is None:
        raise HTTPException(404, "Trajet introuvable")
    try:
        return await scheduler.check_trip(user, trip)
    except TripError as e:
        raise HTTPException(e.status, e.message)


@router.get("/notifications")
async def list_notifications(limit: int = Query(30, ge=1, le=100), user: dict = Depends(current_user)):
    items = await db().list_items(user["_id"], "notifications", limit)
    return {"items": items, "unread": sum(not n.get("read") for n in items)}


@router.post("/notifications/read-all", status_code=204)
async def read_all(user: dict = Depends(current_user)):
    await db().update_all_items(user["_id"], "notifications", {"read": True})


@router.post("/notifications/{notification_id}/read", status_code=204)
async def read_one(notification_id: str, user: dict = Depends(current_user)):
    if not await db().update_item(user["_id"], "notifications", notification_id, {"read": True}):
        raise HTTPException(404, "Notification introuvable")


@router.get("/alerts/config")
def alerts_config():
    return {"email_enabled": mailer.configured(), "scheduler_enabled": scheduler.ENABLED,
            "lead_minutes": scheduler.LEAD_MIN}
