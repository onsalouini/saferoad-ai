# api/services/scheduler.py
"""
Alertes de départ : pour chaque trajet enregistré, une analyse est lancée dans l'heure qui précède
l'heure habituelle de départ (jours choisis, fuseau de l'utilisateur). Le résultat devient une
notification dans l'application, et un e-mail est envoyé si le risque dépasse le seuil du mode
ou si une alerte météo officielle est en cours.

Tourne dans le processus de l'API (une seule instance : ne pas lancer plusieurs workers avec
SCHEDULER_ENABLED=true, sinon les alertes seraient envoyées en double).
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from database import db, new_id

from . import mailer, push
from .shared import acquire_lock
from .trip import TripError, analyse_trip

ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
CHECK_EVERY_S = int(os.getenv("SCHEDULER_INTERVAL_S", "300"))
LEAD_MIN = int(os.getenv("ALERT_LEAD_MIN", "60"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")


def due_date(trip: dict, now_utc: datetime) -> str | None:
    """Date locale (ISO) si le trajet doit être vérifié maintenant, sinon None."""
    local = now_utc.astimezone(ZoneInfo(trip.get("tz") or "UTC"))
    if local.weekday() not in trip.get("days", []):
        return None
    hh, mm = map(int, trip["departure_time"].split(":"))
    minutes_before = (local.replace(hour=hh, minute=mm, second=0, microsecond=0) - local).total_seconds() / 60
    today = local.date().isoformat()
    if 0 <= minutes_before <= LEAD_MIN and trip.get("last_alert_date") != today:
        return today
    return None


def _planned_departure(route: dict, departure_time: str) -> dict:
    """Créneau de la prévision correspondant à l'heure de départ prévue (heure locale du départ)."""
    hh = int(departure_time.split(":")[0])
    for d in route["departures"]:
        if int(d["time"][11:13]) == hh:
            return d
    return route["departures"][0]


async def check_trip(user: dict, trip: dict, local_date: str | None = None) -> dict:
    """Analyse un trajet enregistré et crée la notification correspondante."""
    result = await analyse_trip(trip["origin"], trip["destination"], trip.get("mode", "standard"),
                                profile=trip.get("profile", "standard"))
    i = result["recommended_route"]
    route = result["routes"][i]
    planned = _planned_departure(route, trip["departure_time"])
    best = route["best_departure"]
    threshold = route["summary"]["threshold_used"] * 100
    high = planned["risk_score"] >= threshold
    alerts = result.get("weather_alerts") or []
    name = trip.get("label") or f"{trip['origin'].get('label') or 'Départ'} → {trip['destination'].get('label') or 'Arrivée'}"

    lines = [f"Départ prévu à {trip['departure_time']} : indice {planned['risk_score']:.0f}/100 ({planned['weather_label'].lower()})."]
    if best["time"] != planned["time"] and planned["risk_score"] - best["risk_score"] >= 1:
        lines.append(f"Créneau le plus sûr : {best['time'][11:16]} (indice {best['risk_score']:.0f}, "
                     f"{planned['risk_score'] - best['risk_score']:.0f} points de moins).")
    if len(result["routes"]) > 1:
        lines.append(f"Itinéraire recommandé : n° {i + 1} ({route['distance_km']:.0f} km, {route['duration_min']} min).")
    for a in alerts[:3]:
        lines.append(f"Alerte officielle : {a['event']} ({a['severity_fr']}).")

    notification = {
        "id": new_id(),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trip_id": trip["id"],
        "title": f"{name} : {'risque élevé' if high else 'conditions ' + ('favorables' if planned['status'] == 'good' else 'à surveiller')}",
        "message": " ".join(lines),
        "status": planned["status"],
        "risk_score": planned["risk_score"],
        "high_risk": high,
        "official_alerts": len(alerts),
        "read": False,
    }
    await db().push_item(user["_id"], "notifications", notification)
    if local_date:
        await db().update_item(user["_id"], "saved_trips", trip["id"], {"last_alert_date": local_date})

    await push.notify(user, notification["title"], notification["message"])
    # E-mail uniquement vers une adresse confirmée (évite d'écrire à une adresse saisie par erreur)
    if trip.get("notify_email", True) and user.get("email_verified") and (high or alerts):
        await mailer.send(user["email"], f"SafeRoad AI : {notification['title']}", (
            f"{notification['message']}\n\n"
            f"Voir l'analyse complète : {FRONTEND_URL}/trajet?de={trip['origin']['lat']:.5f},{trip['origin']['lng']:.5f}"
            f"&a={trip['destination']['lat']:.5f},{trip['destination']['lng']:.5f}\n\n"
            "Pour ne plus recevoir ces e-mails, modifiez le trajet dans « Mes trajets ».\nSafeRoad AI"))
    return notification


async def check_all(now_utc: datetime | None = None) -> int:
    now_utc = now_utc or datetime.now(timezone.utc)
    sent = 0
    for user in await db().users_with("saved_trips"):
        for trip in list(user.get("saved_trips") or []):
            date = due_date(trip, now_utc)
            if not date:
                continue
            try:
                await check_trip(user, trip, date)
                sent += 1
            except TripError as e:
                print(f"Alerte non générée ({trip.get('id')}) : {e.message}")
    return sent


async def run_forever() -> None:
    print(f"Planificateur d'alertes actif (toutes les {CHECK_EVERY_S} s, {LEAD_MIN} min avant le départ)")
    while True:
        try:
            # Avec Redis, une seule instance de l'API vérifie les trajets à chaque passage
            if await acquire_lock("scheduler", max(30, CHECK_EVERY_S - 10)):
                await check_all()
        except Exception as e:  # noqa: BLE001 - la boucle ne doit jamais s'arrêter
            print(f"Erreur du planificateur : {type(e).__name__}: {e}")
        await asyncio.sleep(CHECK_EVERY_S)
