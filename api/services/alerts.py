# api/services/alerts.py
"""Alertes météo officielles en cours (National Weather Service, États-Unis, sans clé)."""
from __future__ import annotations

import asyncio
import os

import httpx

from .cache import TTLCache
from .geo import HEADERS

NWS = os.getenv("NWS_URL", "https://api.weather.gov").rstrip("/")
_cache = TTLCache(10 * 60, 500)

SEVERITY_FR = {"Extreme": "Extrême", "Severe": "Sévère", "Moderate": "Modérée", "Minor": "Mineure", "Unknown": "Inconnue"}
SEVERITY_RANK = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1}


async def _at(client: httpx.AsyncClient, lat: float, lng: float) -> list[dict]:
    key = TTLCache.key(round(lat, 2), round(lng, 2))
    hit = _cache.get(key)
    if hit is not None:
        return hit
    r = await client.get(f"{NWS}/alerts/active", params={"point": f"{lat:.4f},{lng:.4f}"},
                         headers={"Accept": "application/geo+json"})
    r.raise_for_status()
    out = []
    for f in r.json().get("features", []):
        p = f.get("properties") or {}
        out.append({
            "id": p.get("id") or f.get("id"),
            "event": p.get("event"),
            "headline": p.get("headline"),
            "severity": p.get("severity", "Unknown"),
            "severity_fr": SEVERITY_FR.get(p.get("severity"), "Inconnue"),
            "area": p.get("areaDesc"),
            "ends": p.get("ends") or p.get("expires"),
            "instruction": (p.get("instruction") or "")[:600] or None,
        })
    _cache.set(key, out)
    return out


async def active_alerts(points: list[tuple[float, float]]) -> list[dict] | None:
    """Alertes NWS sur les points (situés aux États-Unis), dédoublonnées. None si le service échoue."""
    if not points:
        return []
    try:
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as c:  # NWS exige un User-Agent
            results = await asyncio.gather(*[_at(c, lat, lng) for lat, lng in points])
    except httpx.HTTPError as e:
        print(f"NWS indisponible : {e}")
        return None
    seen, out = set(), []
    for alerts in results:
        for a in alerts:
            if a["id"] not in seen:
                seen.add(a["id"])
                out.append(a)
    return sorted(out, key=lambda a: SEVERITY_RANK.get(a["severity"], 0), reverse=True)
