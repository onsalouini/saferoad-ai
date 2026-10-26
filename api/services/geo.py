# api/services/geo.py
"""Géocodage (Nominatim / OpenStreetMap), itinéraires (OSRM) et détection de l'État US."""
from __future__ import annotations

import asyncio
import json
import math
import os
import time
from functools import lru_cache
from pathlib import Path

import httpx

from ml.features import road_class

from .cache import TTLCache

# Instances publiques par défaut ; à remplacer par des instances auto-hébergées en production
NOMINATIM = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org").rstrip("/")
OSRM = os.getenv("OSRM_URL", "https://router.project-osrm.org").rstrip("/")
HEADERS = {"User-Agent": os.getenv("HTTP_USER_AGENT", "SafeRoadAI/3.0 (academic project)"), "Accept-Language": "fr,en"}

# Politique d'usage de Nominatim public : 1 requête par seconde au maximum
NOMINATIM_MIN_INTERVAL_S = float(os.getenv("NOMINATIM_MIN_INTERVAL_S", "1.0"))
_nominatim_lock = asyncio.Lock()
_nominatim_last = 0.0
_search_cache = TTLCache(24 * 3600, 1000)
_route_cache = TTLCache(3600, 300)


async def _nominatim(path: str, params: dict) -> object:
    """Appel Nominatim mis en cache et espacé d'au moins NOMINATIM_MIN_INTERVAL_S."""
    global _nominatim_last
    key = TTLCache.key(path, params)
    hit = _search_cache.get(key)
    if hit is not None:
        return hit
    async with _nominatim_lock:
        wait = NOMINATIM_MIN_INTERVAL_S - (time.monotonic() - _nominatim_last)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as c:
                r = await c.get(f"{NOMINATIM}/{path}", params=params)
                r.raise_for_status()
        finally:
            _nominatim_last = time.monotonic()
    data = r.json()
    _search_cache.set(key, data)
    return data

STATE_CODES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "Puerto Rico": "PR",
}


# ------------------------------------------------------------- État (hors-ligne)
@lru_cache(maxsize=1)
def _states() -> list[tuple[str, list[list[list[float]]], tuple[float, float, float, float]]]:
    path = Path(__file__).resolve().parents[1] / "data" / "us_states.geojson"
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for f in data["features"]:
        code = STATE_CODES.get(f["properties"]["name"])
        geom = f["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        for poly in polys:
            ring = poly[0]
            xs, ys = [p[0] for p in ring], [p[1] for p in ring]
            out.append((code, ring, (min(xs), min(ys), max(xs), max(ys))))
    return out


def _inside(lng: float, lat: float, ring: list[list[float]]) -> bool:
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def state_at(lat: float, lng: float) -> str | None:
    """Code de l'État US contenant le point, ou None hors des États-Unis."""
    for code, ring, (x0, y0, x1, y1) in _states():
        if x0 <= lng <= x1 and y0 <= lat <= y1 and _inside(lng, lat, ring):
            return code
    return None


# ------------------------------------------------------------------ Nominatim
async def search(query: str, limit: int = 6) -> list[dict]:
    items = await _nominatim("search", {"q": query.strip(), "format": "jsonv2", "limit": limit, "addressdetails": 1})
    return [
        {
            "label": item["display_name"],
            "name": item.get("name") or item["display_name"].split(",")[0],
            "lat": float(item["lat"]),
            "lng": float(item["lon"]),
            "country_code": (item.get("address") or {}).get("country_code", "").upper(),
        }
        for item in items
    ]


async def reverse(lat: float, lng: float) -> dict:
    item = await _nominatim("reverse", {
        "lat": round(lat, 5), "lon": round(lng, 5), "format": "jsonv2", "zoom": 14, "addressdetails": 1,
    })
    addr = item.get("address") or {}
    return {
        "label": item.get("display_name", f"{lat:.4f}, {lng:.4f}"),
        "city": addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county"),
        "country_code": addr.get("country_code", "").upper(),
        "state": state_at(lat, lng),
        "lat": lat,
        "lng": lng,
    }


# ----------------------------------------------------------------------- OSRM
async def route(origin: tuple[float, float], destination: tuple[float, float]) -> list[dict]:
    """Itinéraires routiers (lat, lng) -> géométrie [[lat, lng], ...], distance (km), durée (min)."""
    coords = f"{origin[1]:.5f},{origin[0]:.5f};{destination[1]:.5f},{destination[0]:.5f}"
    hit = _route_cache.get(coords)
    if hit is not None:
        return [{**r, "geometry": list(r["geometry"])} for r in hit]
    async with httpx.AsyncClient(timeout=20, headers=HEADERS) as c:
        r = await c.get(f"{OSRM}/route/v1/driving/{coords}", params={
            "overview": "full", "geometries": "geojson", "alternatives": "true", "steps": "true",
        })
        r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("Aucun itinéraire routier trouvé entre ces deux points.")
    routes = []
    for rt in data["routes"]:
        geometry = [[p[1], p[0]] for p in rt["geometry"]["coordinates"]]
        names, classes = _step_roads(rt, len(geometry))
        routes.append({
            "geometry": geometry,
            "road_names": names,
            "road_classes": classes,
            "distance_km": round(rt["distance"] / 1000, 1),
            "duration_min": round(rt["duration"] / 60),
        })
    _route_cache.set(coords, routes)
    return routes


def _step_roads(rt: dict, n_points: int) -> tuple[list[str], list[str]]:
    """Nom et type de route (autoroute / route / rue) pour chaque point de la géométrie complète.

    La géométrie « overview=full » est la concaténation des géométries des étapes (points de jonction
    partagés) : chaque étape couvre len(coordonnées) - 1 points.
    """
    names: list[str] = []
    classes: list[str] = []
    for leg in rt.get("legs", []):
        for step in leg.get("steps", []):
            label = " / ".join(x for x in (step.get("ref"), step.get("name")) if x)
            cls = road_class(step.get("ref"), step.get("name"))
            k = max(1, len(step.get("geometry", {}).get("coordinates", [])) - 1)
            names.extend([label] * k)
            classes.extend([cls] * k)
    if not classes:
        return [""] * n_points, ["local"] * n_points
    names += [names[-1]] * max(0, n_points - len(names))
    classes += [classes[-1]] * max(0, n_points - len(classes))
    return names[:n_points], classes[:n_points]


def haversine_km(a: list[float], b: list[float]) -> float:
    r = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def sample_route(geometry: list[list[float]], n: int) -> list[dict]:
    """n points régulièrement espacés le long de l'itinéraire, avec leur position (km)."""
    cum = [0.0]
    for a, b in zip(geometry, geometry[1:]):
        cum.append(cum[-1] + haversine_km(a, b))
    total = cum[-1] or 1e-9
    out, j = [], 0
    for k in range(n):
        target = total * k / (n - 1) if n > 1 else 0
        while j < len(cum) - 2 and cum[j + 1] < target:
            j += 1
        seg = cum[j + 1] - cum[j] or 1e-9
        t = min(max((target - cum[j]) / seg, 0), 1)
        a, b = geometry[j], geometry[min(j + 1, len(geometry) - 1)]
        out.append({
            "lat": a[0] + (b[0] - a[0]) * t,
            "lng": a[1] + (b[1] - a[1]) * t,
            "km": round(target, 1),
            "index": j,
        })
    return out
