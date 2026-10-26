# api/routes/predict.py
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import optional_user
from database import db, new_id
from ml.predict import model_service
from schemas import SituationInput, TripInput
from services import geo, profiles
from services.trip import OUT_OF_COVERAGE, TripError, analyse_trip

router = APIRouter(tags=["Prédiction"])


def _require_model() -> None:
    if not model_service.ready:
        raise HTTPException(503, f"Modèle indisponible : {model_service.error}")


async def save_history(user: dict | None, kind: str, summary: dict) -> str | None:
    if user is None:
        return None
    entry_id = new_id()
    await db().push_item(user["_id"], "history", {
        "id": entry_id, "kind": kind,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **summary,
    })
    return entry_id


# --------------------------------------------------------------- simulation
@router.post("/predict")
async def predict_situation(body: SituationInput, user: dict | None = Depends(optional_user)):
    """Simulation manuelle : score de risque + facteurs explicatifs."""
    _require_model()
    situation = body.model_dump()
    detected = geo.state_at(body.Start_Lat, body.Start_Lng)
    situation["State"] = (body.State or detected or "").upper()
    result = await asyncio.to_thread(model_service.predict_one, situation, body.mode)
    if body.profile != "standard":
        threshold = profiles.threshold(model_service.thresholds[body.mode], body.profile)
        result.update(threshold_used=threshold, is_high_risk=result["probability"] >= threshold)
    result["profile_advice"] = profiles.PROFILES[body.profile]["advice"]
    result["inputs"] = situation
    result["in_coverage"] = detected is not None
    result["warnings"] = [] if detected else [OUT_OF_COVERAGE]
    result["history_id"] = await save_history(user, "simulation", {
        "title": body.City or f"{body.Start_Lat:.3f}, {body.Start_Lng:.3f}",
        "mode": body.mode, "risk_score": result["risk_score"], "risk_level": result["risk_level"],
        "status": result["status"],
    })
    return result


# ------------------------------------------------------------------- trajet
@router.post("/predict/trip")
async def predict_trip(body: TripInput, user: dict | None = Depends(optional_user)):
    """Analyse complète d'un trajet (voir services/trip.py)."""
    try:
        result = await analyse_trip(body.origin.model_dump(), body.destination.model_dump(), body.mode,
                                    body.road.model_dump(), body.profile)
    except TripError as e:
        raise HTTPException(e.status, e.message)
    main = result["routes"][0]
    result["history_id"] = await save_history(user, "trajet", {
        "title": f"{body.origin.label or 'Départ'} → {body.destination.label or 'Arrivée'}",
        "mode": body.mode,
        "risk_score": main["summary"]["risk_score"],
        "risk_level": main["summary"]["risk_level"],
        "status": main["summary"]["status"],
        "distance_km": main["distance_km"],
        "duration_min": main["duration_min"],
        "best_departure": main["best_departure"],
        "origin": body.origin.model_dump(),
        "destination": body.destination.model_dump(),
    })
    return result
