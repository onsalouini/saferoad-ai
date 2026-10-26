# api/services/incidents.py
"""
Incidents de circulation en temps réel (TomTom Traffic API, offre gratuite avec clé).
Activé seulement si TOMTOM_API_KEY est défini ; sinon la fonction renvoie None.
"""
from __future__ import annotations

import asyncio
import os

import httpx

from .cache import TTLCache

API_KEY = os.getenv("TOMTOM_API_KEY")
URL = "https://api.tomtom.com/traffic/services/5/incidentDetails"
MAX_BOXES = 10
_cache = TTLCache(5 * 60, 300)

CATEGORY_FR = {
    0: "Inconnu", 1: "Accident", 2: "Brouillard", 3: "Conditions dangereuses", 4: "Pluie", 5: "Verglas",
    6: "Bouchon", 7: "Voie fermée", 8: "Route fermée", 9: "Travaux", 10: "Vent", 11: "Inondation",
    14: "Véhicule en panne",
}
DELAY_FR = {0: "inconnu", 1: "faible", 2: "modéré", 3: "important", 4: "route fermée"}


def available() -> bool:
    return bool(API_KEY)


async def _box(client: httpx.AsyncClient, lat: float, lng: float, half: float = 0.08) -> list[dict]:
    bbox = f"{lng - half:.4f},{lat - half:.4f},{lng + half:.4f},{lat + half:.4f}"
    hit = _cache.get(bbox)
    if hit is not None:
        return hit
    r = await client.get(URL, params={
        "key": API_KEY, "bbox": bbox, "language": "fr-FR", "timeValidityFilter": "present",
        "fields": "{incidents{type,geometry{type,coordinates},properties{id,iconCategory,magnitudeOfDelay,events{description},from,to,delay,roadNumbers}}}",
    })
    r.raise_for_status()
    out = []
    for inc in r.json().get("incidents", []):
        p = inc.get("properties") or {}
        coords = (inc.get("geometry") or {}).get("coordinates") or []
        first = coords[0] if coords and isinstance(coords[0], list) else coords
        out.append({
            "id": p.get("id"),
            "category": CATEGORY_FR.get(p.get("iconCategory"), "Incident"),
            "description": "; ".join(e.get("description", "") for e in p.get("events") or [] if e.get("description")),
            "from": p.get("from"), "to": p.get("to"),
            "delay_min": round((p.get("delay") or 0) / 60),
            "delay": DELAY_FR.get(p.get("magnitudeOfDelay"), "inconnu"),
            "road": ", ".join(p.get("roadNumbers") or []),
            "lat": first[1] if len(first) == 2 else None, "lng": first[0] if len(first) == 2 else None,
        })
    _cache.set(bbox, out)
    return out


async def along(points: list[tuple[float, float]]) -> list[dict] | None:
    """Incidents autour des points (cases de 0,16°, au plus MAX_BOXES requêtes). None si désactivé ou en échec."""
    if not API_KEY:
        return None
    cells, boxes = set(), []
    for lat, lng in points:
        cell = (round(lat / 0.16), round(lng / 0.16))
        if cell not in cells:
            cells.add(cell)
            boxes.append((lat, lng))
    step = max(1, -(-len(boxes) // MAX_BOXES))
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            results = await asyncio.gather(*[_box(c, lat, lng) for lat, lng in boxes[::step][:MAX_BOXES]])
    except httpx.HTTPError as e:
        print(f"TomTom indisponible : {e}")
        return None
    seen, out = set(), []
    for incs in results:
        for i in incs:
            if i["id"] not in seen:
                seen.add(i["id"])
                out.append(i)
    return out
