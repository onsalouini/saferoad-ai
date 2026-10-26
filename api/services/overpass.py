# api/services/overpass.py
"""
Données OpenStreetMap (Overpass) le long d'un itinéraire :
- équipements routiers autour de chaque point (US Accidents annote chaque accident avec les
  équipements proches : intersection, feu, passage piéton… ; on reproduit cette annotation) ;
- aires de repos et stations-service pour les pauses.

Les résultats sont gardés dans un cache SQLite persistant (services/diskcache.py).
"""
from __future__ import annotations

import os

import httpx

from . import diskcache
from .geo import HEADERS, haversine_km

OVERPASS = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
RADIUS_M = int(os.getenv("OVERPASS_RADIUS_M", "150"))
# L'instance publique est souvent saturée : on n'attend pas plus de TIMEOUT_S avant de continuer sans
TIMEOUT_S = float(os.getenv("OVERPASS_TIMEOUT_S", "12"))
TTL_S = 30 * 24 * 3600  # les équipements changent rarement

# Variable du modèle -> filtres Overpass (éléments recherchés autour du point)
SELECTORS = {
    "Traffic_Signal": ['node["highway"="traffic_signals"]'],
    "Crossing": ['node["highway"="crossing"]', 'node["railway"="crossing"]'],
    "Stop": ['node["highway"="stop"]'],
    "Give_Way": ['node["highway"="give_way"]'],
    "Roundabout": ['way["junction"="roundabout"]', 'node["highway"="mini_roundabout"]'],
    "Railway": ['node["railway"="level_crossing"]'],
    "Junction": ['node["highway"="motorway_junction"]'],
    "Bump": ['node["traffic_calming"~"^(bump|hump|table)$"]'],
    "Traffic_Calming": ['node["traffic_calming"]'],
    "Station": ['node["railway"="station"]', 'node["public_transport"="station"]'],
    "Amenity": ['node["amenity"~"^(fuel|restaurant|fast_food|cafe|school|hospital|bank|pharmacy)$"]'],
    "No_Exit": ['node["noexit"="yes"]'],
    "Turning_Loop": ['node["highway"="turning_loop"]'],
}


def _classify(tags: dict) -> set[str]:
    found = set()
    hw, rw, tc = tags.get("highway"), tags.get("railway"), tags.get("traffic_calming")
    if hw == "traffic_signals":
        found.add("Traffic_Signal")
    if hw == "crossing" or rw == "crossing":
        found.add("Crossing")
    if hw == "stop":
        found.add("Stop")
    if hw == "give_way":
        found.add("Give_Way")
    if tags.get("junction") == "roundabout" or hw == "mini_roundabout":
        found.add("Roundabout")
    if rw == "level_crossing":
        found.add("Railway")
    if hw == "motorway_junction":
        found.add("Junction")
    if tc:
        found.add("Traffic_Calming")
        if tc in ("bump", "hump", "table"):
            found.add("Bump")
    if rw == "station" or tags.get("public_transport") == "station":
        found.add("Station")
    if tags.get("amenity") in ("fuel", "restaurant", "fast_food", "cafe", "school", "hospital", "bank", "pharmacy"):
        found.add("Amenity")
    if tags.get("noexit") == "yes":
        found.add("No_Exit")
    if hw == "turning_loop":
        found.add("Turning_Loop")
    return found


def _query(points: list[tuple[float, float]]) -> str:
    # Une seule recherche spatiale par point (la partie coûteuse), puis filtrage par étiquettes sur cet ensemble
    near = "".join(f"node(around:{RADIUS_M},{lat:.5f},{lng:.5f});" for lat, lng in points)
    filters = "".join(f"{s.replace('node', 'node.near', 1)};" for sels in SELECTORS.values() for s in sels
                      if s.startswith("node"))
    return (f"[out:json][timeout:{int(TIMEOUT_S)}];({near})->.near;"
            f"({filters}way(bn.near)[\"junction\"=\"roundabout\"];);out tags center;")


def _key(lat: float, lng: float) -> str:
    return f"road:{RADIUS_M}:{lat:.4f},{lng:.4f}"


async def _post(query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=TIMEOUT_S, headers=HEADERS) as c:
        r = await c.post(OVERPASS, data={"data": query})
        r.raise_for_status()
        return r.json().get("elements", [])


async def road_features(points: list[tuple[float, float]]) -> list[dict[str, bool]] | None:
    """Pour chaque point : {variable: présent}. None si Overpass est indisponible pour des points non mis en cache."""
    keys = [_key(lat, lng) for lat, lng in points]
    cached = diskcache.get_many(keys)
    todo = [p for p, k in zip(points, keys) if k not in cached]
    if todo:
        try:
            elements = await _post(_query(todo))
        except (httpx.HTTPError, ValueError) as e:
            print(f"Overpass indisponible : {e}")
            return None
        found: list[set[str]] = [set() for _ in todo]
        radius_km = RADIUS_M / 1000 * 1.05
        for el in elements:
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lng = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lng is None:
                continue
            kinds = _classify(el.get("tags") or {})
            for i, p in enumerate(todo):
                if haversine_km([lat, lng], list(p)) <= radius_km:
                    found[i] |= kinds
        fresh = {_key(*p): {k: k in f for k in SELECTORS} for p, f in zip(todo, found)}
        diskcache.set_many(fresh, TTL_S)
        cached.update(fresh)
    return [cached[k] for k in keys]


async def rest_areas(lat: float, lng: float, radius_km: float = 15) -> list[dict]:
    """Aires de repos, aires de service et stations-service autour d'un point (les plus proches d'abord)."""
    key = f"rest:{radius_km}:{lat:.3f},{lng:.3f}"
    hit = diskcache.get_many([key])
    if key in hit:
        return hit[key]
    r = int(radius_km * 1000)
    query = (f"[out:json][timeout:{int(TIMEOUT_S)}];("
             f"nwr(around:{r},{lat:.4f},{lng:.4f})[\"highway\"~\"^(rest_area|services)$\"];"
             f"node(around:{r},{lat:.4f},{lng:.4f})[\"amenity\"=\"fuel\"];"
             f");out tags center 40;")
    elements = await _post(query)
    out = []
    for el in elements:
        plat = el.get("lat") or (el.get("center") or {}).get("lat")
        plng = el.get("lon") or (el.get("center") or {}).get("lon")
        if plat is None:
            continue
        tags = el.get("tags") or {}
        kind = {"rest_area": "Aire de repos", "services": "Aire de service"}.get(tags.get("highway"), "Station-service")
        out.append({"name": tags.get("name") or tags.get("brand") or kind, "kind": kind, "lat": plat, "lng": plng,
                    "distance_km": round(haversine_km([lat, lng], [plat, plng]), 1)})
    out.sort(key=lambda x: (x["kind"] == "Station-service", x["distance_km"]))
    diskcache.set_many({key: out[:8]}, 7 * 24 * 3600)
    return out[:8]
