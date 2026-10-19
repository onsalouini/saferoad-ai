# api/routes/geo.py
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query

from services import geo, weather

router = APIRouter(tags=["Localisation & météo"])


@router.get("/geo/search")
async def search(q: str = Query(..., min_length=2, max_length=200)):
    try:
        return await geo.search(q)
    except httpx.HTTPError:
        raise HTTPException(502, "Service de géocodage indisponible")


@router.get("/geo/reverse")
async def reverse(lat: float = Query(..., ge=-90, le=90), lng: float = Query(..., ge=-180, le=180)):
    try:
        return await geo.reverse(lat, lng)
    except httpx.HTTPError:
        return {"label": f"{lat:.4f}, {lng:.4f}", "state": geo.state_at(lat, lng), "lat": lat, "lng": lng}


@router.get("/weather")
async def current_weather(lat: float = Query(..., ge=-90, le=90), lng: float = Query(..., ge=-180, le=180)):
    """Météo actuelle convertie au format du modèle (pré-remplissage du simulateur)."""
    try:
        w = await weather.current(lat, lng)
    except httpx.HTTPError:
        raise HTTPException(502, "Service météo indisponible")
    return {**w, "State": geo.state_at(lat, lng)}
