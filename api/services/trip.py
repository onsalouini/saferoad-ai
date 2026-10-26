# api/services/trip.py
"""
Analyse complète d'un trajet, partagée par l'API, le copilote IA et les alertes planifiées :
itinéraires (OSRM, avec le type de route de chaque tronçon) -> points échantillonnés
-> météo prévue à l'heure de passage (Open-Meteo) + équipements routiers (Overpass)
+ alertes officielles (NWS) + incidents (TomTom, si clé) + signalements des utilisateurs
-> risque par tronçon -> comparaison des itinéraires -> meilleure heure de départ (24 h)
+ éblouissement par le soleil, pauses conseillées et règles propres au profil de conducteur.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from database import db
from ml.features import GROUP_LABELS, ROAD_FEATURES
from ml.predict import model_service

from . import alerts, geo, incidents, overpass, profiles, sun, weather

HORIZON_H = 24
MAX_ALERT_POINTS = 8
PAUSE_EVERY_MIN = 120       # pause conseillée toutes les 2 h (sécurité routière)
REPORT_RADIUS_KM = 1.0      # signalements pris en compte à moins de 1 km de l'itinéraire
SUNNY = {"Clear", "Fair", "Fair / Windy", "Partly Cloudy", "Scattered Clouds"}
OUT_OF_COVERAGE = (
    "Point situé hors des États-Unis : le modèle a été entraîné uniquement sur des accidents "
    "américains (US Accidents). Le score est extrapolé et doit être considéré comme indicatif."
)
ROAD_CLASS_FR = {"freeway": "autoroute", "highway": "route", "local": "rue"}


class TripError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _n_samples(distance_km: float) -> int:
    return int(min(12, max(5, round(distance_km / 20) + 4)))


def _alert_points(samples: list[list[dict]]) -> list[tuple[float, float]]:
    """Points aux États-Unis, un par case de 0,25°, au plus MAX_ALERT_POINTS."""
    seen, out = set(), []
    for pts in samples:
        for p in pts:
            if p["state"] is None:
                continue
            cell = (round(p["lat"] * 4), round(p["lng"] * 4))
            if cell not in seen:
                seen.add(cell)
                out.append((p["lat"], p["lng"]))
    step = max(1, -(-len(out) // MAX_ALERT_POINTS))  # division arrondie au supérieur
    return out[::step][:MAX_ALERT_POINTS]


def _pauses(route: dict, every_min: int) -> list[dict]:
    """Points de pause conseillés le long de l'itinéraire (toutes les `every_min` minutes de conduite)."""
    if route["duration_min"] <= every_min:
        return []
    geom = route["geometry"]
    cum = [0.0]
    for a, b in zip(geom, geom[1:]):
        cum.append(cum[-1] + geo.haversine_km(a, b))
    total = cum[-1] or 1e-9
    out, j = [], 0
    for m in range(every_min, route["duration_min"] - 20, every_min):
        target = total * m / route["duration_min"]
        while j < len(cum) - 1 and cum[j] < target:
            j += 1
        out.append({"after_min": m, "km": round(target), "lat": geom[j][0], "lng": geom[j][1]})
    return out


def _near_route(items: list[dict], geometry: list[list[float]], radius_km: float) -> list[dict]:
    pts = geometry[:: max(1, len(geometry) // 400)]
    out = []
    for it in items:
        if it.get("lat") is None:
            continue
        d = min(geo.haversine_km([it["lat"], it["lng"]], p) for p in pts)
        if d <= radius_km:
            out.append({**it, "distance_km": round(d, 2)})
    return out


async def _reports_along(routes: list[dict]) -> list[dict]:
    lats = [p[0] for r in routes for p in r["geometry"]]
    lngs = [p[1] for r in routes for p in r["geometry"]]
    pad = REPORT_RADIUS_KM / 100
    bbox = (min(lats) - pad, min(lngs) - pad, max(lats) + pad, max(lngs) + pad)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    found = await db().list_reports(bbox, now)
    return [{k: v for k, v in r.items() if k not in ("voters", "user_id")} for r in found]


async def analyse_trip(origin: dict, destination: dict, mode: str = "standard", road: dict | None = None,
                       profile: str = "standard") -> dict:
    if not model_service.ready:
        raise TripError(503, f"Modèle indisponible : {model_service.error}")
    road = {f: bool((road or {}).get(f)) for f in ROAD_FEATURES}
    prof = profiles.PROFILES.get(profile, profiles.PROFILES["standard"])
    threshold = profiles.threshold(model_service.thresholds.get(mode, model_service.thresholds["standard"]), profile)
    o, d = (origin["lat"], origin["lng"]), (destination["lat"], destination["lng"])
    try:
        routes = await geo.route(o, d)
    except ValueError as e:
        raise TripError(422, str(e))
    except httpx.HTTPError:
        raise TripError(502, "Service d'itinéraire (OSRM) indisponible, réessayez.")

    samples = [geo.sample_route(r["geometry"], _n_samples(r["distance_km"])) for r in routes]
    for r, pts in zip(routes, samples):
        for p in pts:
            p["state"] = geo.state_at(p["lat"], p["lng"])
            i = min(p["index"], len(r["road_classes"]) - 1)
            p["road_class"], p["road_name"] = r["road_classes"][i], r["road_names"][i]
            p["heading"] = sun.heading_at(r["geometry"], p["index"])
    flat = [(p["lat"], p["lng"]) for pts in samples for p in pts]

    forecasts, detected, official, traffic, reports = await asyncio.gather(
        weather.hourly_forecast(flat, hours=HORIZON_H + 12),
        overpass.road_features(flat),
        alerts.active_alerts(_alert_points(samples)),
        incidents.along(flat),
        _reports_along(routes),
        return_exceptions=True,
    )
    if isinstance(forecasts, BaseException):
        if isinstance(forecasts, httpx.HTTPError):
            raise TripError(502, "Service météo (Open-Meteo) indisponible, réessayez.")
        raise forecasts
    detected, official, traffic, reports = (
        None if isinstance(x, BaseException) else x for x in (detected, official, traffic, reports))

    analysed, k = [], 0
    for r, pts in zip(routes, samples):
        for p in pts:
            p["forecast"] = forecasts[k]
            osm = detected[k] if detected else {}
            p["road"] = {f: road[f] or bool(osm.get(f)) for f in ROAD_FEATURES}
            k += 1
        n_hours = min(HORIZON_H, min(len(p["forecast"]) for p in pts))

        def at(p: dict, h: int) -> dict:
            offset = round(p["km"] / max(r["distance_km"], 0.1) * r["duration_min"] / 60)
            return p["forecast"][min(h + offset, len(p["forecast"]) - 1)]

        # Situations : départ à h, passage au point i à h + (km_i / km_total) * durée
        situations, index = [], []
        for h in range(n_hours):
            for i, p in enumerate(pts):
                situations.append({**at(p, h), **p["road"], "Road_Class": p["road_class"],
                                   "Start_Lat": p["lat"], "Start_Lng": p["lng"], "State": p["state"] or ""})
                index.append((h, i))
        # LightGBM hors de la boucle asynchrone : l'API reste disponible pendant le calcul
        probas = await asyncio.to_thread(model_service.probabilities, situations)
        grid = [[0.0] * len(pts) for _ in range(n_hours)]
        for (h, i), pr in zip(index, probas):
            grid[h][i] = float(pr)

        departures = []
        for h in range(n_hours):
            row = grid[h]
            mean = sum(row) / len(row)
            glare_n = sum(1 for p in pts if at(p, h)["Weather_Condition"] in SUNNY
                          and sun.glare(p["lat"], p["lng"], p["heading"], at(p, h)["time"], at(p, h).get("utc_offset_s", 0)))
            departures.append({
                "time": pts[0]["forecast"][h]["time"],
                "risk_score": round(mean * 100, 1),
                "peak_score": round(max(row) * 100, 1),
                "status": model_service.level(mean)["status"],
                "weather_label": pts[0]["forecast"][h]["weather_label"],
                "glare_segments": glare_n,
            })

        now = grid[0]
        segments = []
        for i, p in enumerate(pts):
            w = at(p, 0)
            g = sun.glare(p["lat"], p["lng"], p["heading"], w["time"], w.get("utc_offset_s", 0)) \
                if w["Weather_Condition"] in SUNNY else None
            segments.append({
                "lat": p["lat"], "lng": p["lng"], "km": p["km"], "geometry_index": p["index"],
                "state": p["state"], "in_coverage": p["state"] is not None,
                "weather": {kk: w[kk] for kk in ("weather_label", "Weather_Condition", "Temperature_F",
                                                  "Visibility_mi", "Wind_Speed_mph", "Precipitation_in",
                                                  "IsNight", "time")},
                "road": [GROUP_LABELS[f] for f in ROAD_FEATURES if p["road"][f]],
                "road_class": p["road_class"],
                "road_name": p["road_name"],
                "heading": round(p["heading"]),
                "glare": g,
                **model_service.assess(now[i], mode, threshold),
            })
        mean_now = sum(now) / len(now)
        worst = max(range(len(pts)), key=lambda i: now[i])
        worst_situation = situations[index.index((0, worst))]
        explanation = await asyncio.to_thread(model_service.explain, worst_situation)
        analysed.append({
            "geometry": r["geometry"],
            "road_share": {c: round(sum(s == c for s in r["road_classes"]) / max(len(r["road_classes"]), 1), 3)
                           for c in ("freeway", "highway", "local")},
            "distance_km": r["distance_km"],
            "duration_min": r["duration_min"],
            "summary": model_service.assess(mean_now, mode, threshold),
            "peak": {**model_service.assess(now[worst], mode, threshold), "km": pts[worst]["km"]},
            "segments": segments,
            "departures": departures,
            "best_departure": min(departures, key=lambda x: (x["risk_score"], x["glare_segments"])),
            "explanation": explanation,
            "coverage": sum(s["in_coverage"] for s in segments) / len(segments),
            "pauses": _pauses(r, prof.get("pause_every_min", PAUSE_EVERY_MIN)),
            "incidents": _near_route(traffic, r["geometry"], 0.5) if traffic is not None else None,
            "reports": _near_route(reports, r["geometry"], REPORT_RADIUS_KM) if reports is not None else [],
        })

    # Itinéraire le plus sûr ; à risque quasi égal (< 0,5 pt), le plus rapide l'emporte
    best_idx = min(range(len(analysed)), key=lambda i: (
        round(analysed[i]["summary"]["risk_score"] * 2) / 2, analysed[i]["duration_min"]))
    for i, a in enumerate(analysed):
        a["recommended"] = i == best_idx
    main = analysed[best_idx]

    warnings = []
    if any(a["coverage"] < 1 for a in analysed):
        warnings.append(OUT_OF_COVERAGE)
    if detected is None:
        warnings.append("Équipements routiers (intersections, feux…) indisponibles (OpenStreetMap / Overpass ne répond pas) : "
                        "seuls ceux cochés manuellement sont pris en compte.")
    if official:
        warnings.append(f"{len(official)} alerte(s) météo officielle(s) en cours sur le trajet (National Weather Service).")
    glare_now = [s for s in main["segments"] if s["glare"]]
    if glare_now:
        warnings.append(f"Soleil bas face à vous sur {len(glare_now)} tronçon(s) au départ immédiat "
                        f"(km {', '.join(str(round(s['km'])) for s in glare_now[:4])}) : risque d'éblouissement, "
                        "prévoyez des lunettes de soleil et le pare-soleil.")
    if main["incidents"]:
        warnings.append(f"{len(main['incidents'])} incident(s) de circulation en cours sur l'itinéraire recommandé.")
    if main["reports"]:
        warnings.append(f"{len(main['reports'])} signalement(s) d'utilisateurs à proximité de l'itinéraire recommandé.")
    warnings += profiles.checks(profile, main["segments"])

    return {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "profile": profile,
        "profile_label": prof["label"],
        "profile_advice": prof["advice"],
        "threshold_used": threshold,
        "routes": analysed,
        "recommended_route": best_idx,
        "weather_alerts": official,
        "road_source": "openstreetmap" if detected is not None else "manuel",
        "traffic_source": "tomtom" if traffic is not None else None,
        "warnings": warnings,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def compact(result: dict, route_index: int | None = None) -> dict:
    """Résumé d'une analyse, pour le copilote IA et les notifications (même forme que lib/assistant.js)."""
    i = result["recommended_route"] if route_index is None else route_index
    route = result["routes"][i]
    s = route["summary"]
    pick = lambda d: {"heure": d["time"], "indice": d["risk_score"], "niveau": d["status"], "meteo": d["weather_label"]}  # noqa: E731
    return {
        "type": "analyse_de_trajet",
        "origine": result["origin"].get("label"),
        "destination": result["destination"].get("label"),
        "mode_alerte": result["mode"],
        "profil": result.get("profile_label"),
        "genere_le": result["generated_at"],
        "itineraire_affiche": i + 1,
        "distance_km": route["distance_km"],
        "duree_min": route["duration_min"],
        "part_autoroute": route.get("road_share", {}).get("freeway"),
        "indice_moyen_depart_immediat": s["risk_score"],
        "niveau": s["risk_level"],
        "seuil_alerte": round(s["threshold_used"] * 100),
        "alerte": s["is_high_risk"],
        "troncon_le_plus_risque": {"km": route["peak"]["km"], "indice": route["peak"]["risk_score"]},
        "depart_immediat": pick(route["departures"][0]),
        "meilleur_depart": pick(route["best_departure"]),
        "itineraires": [{"numero": j + 1, "distance_km": r["distance_km"], "duree_min": r["duration_min"],
                         "indice": r["summary"]["risk_score"], "recommande": r["recommended"]}
                        for j, r in enumerate(result["routes"])],
        "facteurs_principaux": [{"facteur": f["label"], "impact": f["impact"]} for f in route["explanation"]["factors"]],
        "troncons": [{"km": x["km"], "etat_us": x["state"], "meteo": x["weather"]["weather_label"],
                      "temperature_c": round((x["weather"]["Temperature_F"] - 32) * 5 / 9),
                      "nuit": x["weather"]["IsNight"], "equipements": x["road"],
                      "type_route": ROAD_CLASS_FR.get(x["road_class"], x["road_class"]), "route": x["road_name"],
                      "eblouissement": bool(x.get("glare")), "indice": x["risk_score"]}
                     for x in route["segments"]],
        "pauses_conseillees": [{"apres_min": p["after_min"], "km": p["km"]} for p in route.get("pauses") or []],
        "incidents": [{"type": x["category"], "description": x["description"], "retard_min": x["delay_min"]}
                      for x in route.get("incidents") or []],
        "signalements": [{"type": x["type"], "commentaire": x.get("comment"), "confirmations": x.get("confirmations", 0)}
                         for x in route.get("reports") or []],
        "alertes_officielles": [{"evenement": a["event"], "gravite": a["severity_fr"], "zone": a["area"], "fin": a["ends"]}
                                for a in result.get("weather_alerts") or []],
        "avertissements": result["warnings"],
    }
