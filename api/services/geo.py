# api/services/geo.py
"""Géocodage (Nominatim / OpenStreetMap), itinéraires (OSRM) et détection de l'État US."""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import httpx

NOMINATIM = "https://nominatim.openstreetmap.org"
OSRM = "https://router.project-osrm.org"
HEADERS = {"User-Agent": "SafeRoadAI/1.0 (academic project)", "Accept-Language": "fr,en"}

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
    async with httpx.AsyncClient(timeout=10, headers=HEADERS) as c:
        r = await c.get(f"{NOMINATIM}/search", params={
            "q": query, "format": "jsonv2", "limit": limit, "addressdetails": 1,
        })
        r.raise_for_status()
    return [
        {
            "label": item["display_name"],
            "name": item.get("name") or item["display_name"].split(",")[0],
            "lat": float(item["lat"]),
            "lng": float(item["lon"]),
            "country_code": (item.get("address") or {}).get("country_code", "").upper(),
        }
        for item in r.json()
    ]


async def reverse(lat: float, lng: float) -> dict:
    async with httpx.AsyncClient(timeout=10, headers=HEADERS) as c:
        r = await c.get(f"{NOMINATIM}/reverse", params={
            "lat": lat, "lon": lng, "format": "jsonv2", "zoom": 14, "addressdetails": 1,
        })
        r.raise_for_status()
    item = r.json()
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
async def route(origin: tuple[float, float], destination: tuple[float, float]) -> dict:
    """Itinéraire routier (lat, lng) -> géométrie [[lat, lng], ...], distance (km), durée (min)."""
    coords = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    async with httpx.AsyncClient(timeout=20, headers=HEADERS) as c:
        r = await c.get(f"{OSRM}/route/v1/driving/{coords}", params={
            "overview": "full", "geometries": "geojson", "alternatives": "true",
        })
        r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("Aucun itinéraire routier trouvé entre ces deux points.")
    return [
        {
            "geometry": [[p[1], p[0]] for p in rt["geometry"]["coordinates"]],
            "distance_km": round(rt["distance"] / 1000, 1),
            "duration_min": round(rt["duration"] / 60),
        }
        for rt in data["routes"]
    ]


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
