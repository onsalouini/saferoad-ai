# api/routes/predict.py
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException

from auth import optional_user
from database import db
from ml.predict import model_service
from schemas import SituationInput, TripInput
from services import geo, weather

router = APIRouter(tags=["Prédiction"])

HORIZON_H = 24
OUT_OF_COVERAGE = (
    "Point situé hors des États-Unis : le modèle a été entraîné uniquement sur des accidents "
    "américains (US Accidents). Le score est extrapolé et doit être considéré comme indicatif."
)


def _require_model() -> None:
    if not model_service.ready:
        raise HTTPException(503, f"Modèle indisponible : {model_service.error}")


async def _save(user: dict | None, kind: str, summary: dict) -> str | None:
    if user is None:
        return None
    return await db().insert("history", {
        "user_id": user["_id"], "kind": kind,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **summary,
    })


# --------------------------------------------------------------- simulation
@router.post("/predict")
async def predict_situation(body: SituationInput, user: dict | None = Depends(optional_user)):
    """Simulation manuelle : score de risque + facteurs explicatifs."""
    _require_model()
    situation = body.model_dump()
    detected = geo.state_at(body.Start_Lat, body.Start_Lng)
    situation["State"] = (body.State or detected or "").upper()
    result = model_service.predict_one(situation, body.mode)
    result["inputs"] = situation
    result["in_coverage"] = detected is not None
    result["warnings"] = [] if detected else [OUT_OF_COVERAGE]
    result["history_id"] = await _save(user, "simulation", {
        "title": body.City or f"{body.Start_Lat:.3f}, {body.Start_Lng:.3f}",
        "mode": body.mode, "risk_score": result["risk_score"], "risk_level": result["risk_level"],
        "status": result["status"],
    })
    return result


# ------------------------------------------------------------------- trajet
def _n_samples(distance_km: float) -> int:
    return int(min(12, max(5, round(distance_km / 20) + 4)))


@router.post("/predict/trip")
async def predict_trip(body: TripInput, user: dict | None = Depends(optional_user)):
    """
    Analyse complète d'un trajet :
    itinéraires (OSRM) -> points échantillonnés -> météo prévue à l'heure de passage (Open-Meteo)
    -> risque par segment -> comparaison des itinéraires -> meilleure heure de départ (24 h).
    """
    _require_model()
    o, d = (body.origin.lat, body.origin.lng), (body.destination.lat, body.destination.lng)
    try:
        routes = await geo.route(o, d)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except httpx.HTTPError:
        raise HTTPException(502, "Service d'itinéraire (OSRM) indisponible, réessayez.")

    # Points échantillonnés sur chaque itinéraire, météo en un seul appel
    samples = [geo.sample_route(r["geometry"], _n_samples(r["distance_km"])) for r in routes]
    flat = [(p["lat"], p["lng"]) for pts in samples for p in pts]
    try:
        forecasts = await weather.hourly_forecast(flat, hours=HORIZON_H + 12)
    except httpx.HTTPError:
        raise HTTPException(502, "Service météo (Open-Meteo) indisponible, réessayez.")
    road = body.road.model_dump()

    analysed, k = [], 0
    for r, pts in zip(routes, samples):
        for p in pts:
            p["state"] = geo.state_at(p["lat"], p["lng"])
            p["forecast"] = forecasts[k]
            k += 1
        n_hours = min(HORIZON_H, min(len(p["forecast"]) for p in pts))

        # Situations : départ à h, passage au point i à h + (km_i / km_total) * durée
        situations, index = [], []
        for h in range(n_hours):
            for i, p in enumerate(pts):
                offset = round(p["km"] / max(r["distance_km"], 0.1) * r["duration_min"] / 60)
                w = p["forecast"][min(h + offset, len(p["forecast"]) - 1)]
                situations.append({**w, **road, "Start_Lat": p["lat"], "Start_Lng": p["lng"],
                                   "State": p["state"] or ""})
                index.append((h, i))
        probas = model_service.probabilities(situations)

        grid = [[0.0] * len(pts) for _ in range(n_hours)]
        for (h, i), pr in zip(index, probas):
            grid[h][i] = float(pr)

        departures = []
        for h in range(n_hours):
            row = grid[h]
            mean = sum(row) / len(row)
            departures.append({
                "time": pts[0]["forecast"][h]["time"],
                "risk_score": round(mean * 100, 1),
                "peak_score": round(max(row) * 100, 1),
                "status": model_service.level(mean)["status"],
                "weather_label": pts[0]["forecast"][h]["weather_label"],
            })

        # Maintenant (h = 0) : détail par segment
        now = grid[0]
        segments = []
        for i, p in enumerate(pts):
            offset = round(p["km"] / max(r["distance_km"], 0.1) * r["duration_min"] / 60)
            w = p["forecast"][min(offset, len(p["forecast"]) - 1)]
            segments.append({
                "lat": p["lat"], "lng": p["lng"], "km": p["km"], "geometry_index": p["index"],
                "state": p["state"], "in_coverage": p["state"] is not None,
                "weather": {kk: w[kk] for kk in ("weather_label", "Weather_Condition", "Temperature_F",
                                                  "Visibility_mi", "Wind_Speed_mph", "Precipitation_in",
                                                  "IsNight", "time")},
                **model_service.assess(now[i], body.mode),
            })
        mean_now = sum(now) / len(now)
        worst = max(range(len(pts)), key=lambda i: now[i])
        worst_situation = situations[index.index((0, worst))]
        analysed.append({
            "geometry": r["geometry"],
            "distance_km": r["distance_km"],
            "duration_min": r["duration_min"],
            "summary": model_service.assess(mean_now, body.mode),
            "peak": {**model_service.assess(now[worst], body.mode), "km": pts[worst]["km"]},
            "segments": segments,
            "departures": departures,
            "best_departure": min(departures, key=lambda x: x["risk_score"]),
            "explanation": model_service.explain(worst_situation),
            "coverage": sum(s["in_coverage"] for s in segments) / len(segments),
        })

    # Itinéraire le plus sûr ; à risque quasi égal (< 0,5 pt), le plus rapide l'emporte
    best_idx = min(range(len(analysed)), key=lambda i: (
        round(analysed[i]["summary"]["risk_score"] * 2) / 2, analysed[i]["duration_min"]))
    for i, a in enumerate(analysed):
        a["recommended"] = i == best_idx
    main = analysed[0]

    warnings = []
    if any(a["coverage"] < 1 for a in analysed):
        warnings.append(OUT_OF_COVERAGE)
    if not any(road.values()):
        warnings.append("Les caractéristiques de la route (intersections, feux…) ne sont pas connues "
                        "sur l'itinéraire : elles sont considérées comme absentes.")

    result = {
        "origin": body.origin.model_dump(),
        "destination": body.destination.model_dump(),
        "mode": body.mode,
        "routes": analysed,
        "recommended_route": best_idx,
        "warnings": warnings,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    result["history_id"] = await _save(user, "trajet", {
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
