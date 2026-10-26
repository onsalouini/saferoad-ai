# api/services/weather.py
"""Météo actuelle et prévisions horaires (Open-Meteo, sans clé), converties au format du modèle."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone

import httpx

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
HPA_TO_INHG = 0.0295300
M_TO_MI = 1 / 1609.344

HOURLY = [
    "temperature_2m", "relative_humidity_2m", "pressure_msl", "visibility",
    "wind_speed_10m", "precipitation", "weather_code", "is_day",
]

# Code météo WMO -> (catégorie du modèle, libellé français)
WMO = {
    0: ("Fair", "Ciel dégagé"),
    1: ("Fair", "Plutôt dégagé"),
    2: ("Partly Cloudy", "Partiellement nuageux"),
    3: ("Overcast", "Couvert"),
    45: ("Fog", "Brouillard"),
    48: ("Fog", "Brouillard givrant"),
    51: ("Light Drizzle", "Bruine légère"),
    53: ("Light Drizzle", "Bruine"),
    55: ("Light Drizzle", "Bruine dense"),
    56: ("Other", "Bruine verglaçante"),
    57: ("Other", "Bruine verglaçante dense"),
    61: ("Light Rain", "Pluie faible"),
    63: ("Rain", "Pluie"),
    65: ("Heavy Rain", "Pluie forte"),
    66: ("Other", "Pluie verglaçante"),
    67: ("Other", "Pluie verglaçante forte"),
    71: ("Light Snow", "Neige faible"),
    73: ("Light Snow", "Neige"),
    75: ("Other", "Neige forte"),
    77: ("Light Snow", "Grains de neige"),
    80: ("Light Rain", "Averses faibles"),
    81: ("Rain", "Averses"),
    82: ("Heavy Rain", "Averses violentes"),
    85: ("Light Snow", "Averses de neige"),
    86: ("Other", "Fortes averses de neige"),
    95: ("Other", "Orage"),
    96: ("Other", "Orage avec grêle"),
    99: ("Other", "Orage violent avec grêle"),
}


_CACHE: dict[str, tuple[float, object]] = {}
CACHE_TTL_S = 15 * 60


async def _fetch(params: dict) -> object:
    """Appel Open-Meteo avec cache (15 min) et nouvelles tentatives sur 429 / 5xx / délai dépassé."""
    key = json.dumps(params, sort_keys=True)
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
        return hit[1]
    last: Exception | None = None
    async with httpx.AsyncClient(timeout=20) as c:
        for attempt in range(3):
            try:
                r = await c.get(OPEN_METEO, params=params)
                if r.status_code == 429 or r.status_code >= 500:
                    raise httpx.HTTPStatusError(f"Open-Meteo {r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                data = r.json()
                if len(_CACHE) > 500:
                    _CACHE.clear()
                _CACHE[key] = (time.monotonic(), data)
                return data
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as e:
                last = e
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500 and e.response.status_code != 429:
                    break
                await asyncio.sleep(1.0 * (attempt + 1))
    print(f"Open-Meteo indisponible : {last}")
    raise last


def _to_model(values: dict, i: int) -> dict:
    code = int(values["weather_code"][i] or 0)
    category, label = WMO.get(code, ("Other", "Conditions inconnues"))
    wind = float(values["wind_speed_10m"][i] or 0)
    if category == "Fair" and wind >= 20:
        category = "Fair / Windy"
    vis = values["visibility"][i]
    return {
        "Temperature_F": round(float(values["temperature_2m"][i]), 1),
        "Humidity": float(values["relative_humidity_2m"][i]),
        "Pressure": round(float(values["pressure_msl"][i]) * HPA_TO_INHG, 2),
        # US Accidents plafonne la visibilité autour de 10 mi
        "Visibility_mi": round(min(float(vis) * M_TO_MI, 10.0), 1) if vis is not None else 10.0,
        "Wind_Speed_mph": round(wind, 1),
        "Precipitation_in": round(float(values["precipitation"][i] or 0), 3),
        "Weather_Condition": category,
        "weather_label": label,
        "weather_code": code,
        "IsNight": not bool(values["is_day"][i]),
    }


async def hourly_forecast(points: list[tuple[float, float]], hours: int = 24) -> list[list[dict]]:
    """
    Prévisions horaires pour plusieurs points en un seul appel.
    Renvoie, pour chaque point, une liste de `hours` situations météo
    (heure locale), en commençant par l'heure courante.
    """
    params = {
        "latitude": ",".join(f"{p[0]:.4f}" for p in points),
        "longitude": ",".join(f"{p[1]:.4f}" for p in points),
        "hourly": ",".join(HOURLY),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
        "forecast_days": 3,
    }
    payload = await _fetch(params)
    if isinstance(payload, dict):
        payload = [payload]

    out = []
    for loc in payload:
        h = loc["hourly"]
        times = [datetime.fromisoformat(t) for t in h["time"]]  # heure locale, naïve
        now_local = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            seconds=loc.get("utc_offset_seconds", 0))
        # dernière heure entamée
        start = max((i for i, t in enumerate(times) if t <= now_local), default=0)
        series = []
        for i in range(start, min(start + hours, len(times))):
            w = _to_model(h, i)
            t = times[i]
            w.update({
                "time": t.isoformat(timespec="minutes"),
                "Hour": t.hour,
                "DayOfWeek": t.weekday(),  # 0 = lundi
                "Month": t.month,
                "utc_offset_s": loc.get("utc_offset_seconds", 0),
            })
            series.append(w)
        out.append(series)
    return out


async def current(lat: float, lng: float) -> dict:
    return (await hourly_forecast([(lat, lng)], hours=1))[0][0]
