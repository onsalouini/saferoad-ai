from datetime import datetime, timezone

import pytest

from services import scheduler


def await_(coro):
    import asyncio
    return asyncio.new_event_loop().run_until_complete(coro)

TRIP = {
    "origin": {"lat": 39.7589, "lng": -84.1916, "label": "Dayton"},
    "destination": {"lat": 39.9612, "lng": -82.9988, "label": "Columbus"},
    "departure_time": "08:00", "days": [0, 1, 2, 3, 4], "tz": "America/New_York",
}


def fake_result(score: float, alerts=None) -> dict:
    deps = [{"time": f"2026-10-26T{h:02d}:00", "risk_score": score - (h == 10) * 10, "peak_score": score,
             "status": "serious" if score >= 65 else "good", "weather_label": "Pluie"} for h in range(7, 12)]
    route = {"departures": deps, "best_departure": min(deps, key=lambda d: d["risk_score"]),
             "summary": {"threshold_used": 0.65}, "distance_km": 115, "duration_min": 70}
    return {"recommended_route": 0, "routes": [route], "weather_alerts": alerts or []}


def test_saved_trip_crud(account):
    c, _, _ = account
    r = c.post("/trips", json=TRIP)
    assert r.status_code == 201
    trip_id = r.json()["id"]
    assert [t["id"] for t in c.get("/trips").json()] == [trip_id]
    assert c.delete(f"/trips/{trip_id}").status_code == 204
    assert c.get("/trips").json() == []


@pytest.mark.parametrize("bad", [{"departure_time": "25:00"}, {"days": [7]}, {"tz": "Mars/Olympus"}])
def test_saved_trip_validation(account, bad):
    c, _, _ = account
    assert c.post("/trips", json={**TRIP, **bad}).status_code == 422


def test_due_date_window():
    trip = {**TRIP, "id": "t"}
    # lundi 26/10/2026, 07:30 à New York = 11:30 UTC -> dans l'heure qui précède 08:00
    assert scheduler.due_date(trip, datetime(2026, 10, 26, 11, 30, tzinfo=timezone.utc)) == "2026-10-26"
    assert scheduler.due_date(trip, datetime(2026, 10, 26, 12, 30, tzinfo=timezone.utc)) is None  # départ passé
    assert scheduler.due_date(trip, datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc)) is None    # trop tôt
    assert scheduler.due_date(trip, datetime(2026, 10, 25, 11, 30, tzinfo=timezone.utc)) is None   # dimanche
    assert scheduler.due_date({**trip, "last_alert_date": "2026-10-26"},
                              datetime(2026, 10, 26, 11, 30, tzinfo=timezone.utc)) is None        # déjà envoyé


def test_check_creates_notification_and_emails_on_high_risk(account, monkeypatch):
    c, email, _ = account
    sent = []

    async def fake_analyse(*args, **kwargs):
        return fake_result(72, alerts=[{"event": "Flood Warning", "severity_fr": "Sévère"}])

    async def fake_send(to, subject, text):
        sent.append((to, subject))
        return True

    monkeypatch.setattr(scheduler, "analyse_trip", fake_analyse)
    monkeypatch.setattr(scheduler.mailer, "send", fake_send)
    from database import db
    user = await_(db().get_user_by_email(email))
    await_(db().update_user(user["_id"], {"email_verified": True}))
    trip_id = c.post("/trips", json=TRIP).json()["id"]

    n = c.post(f"/trips/{trip_id}/check").json()
    assert n["high_risk"] and n["risk_score"] == 72 and n["official_alerts"] == 1
    assert "10:00" in n["message"]  # meilleur créneau proposé
    assert sent and sent[0][0] == email

    notes = c.get("/notifications").json()
    assert notes["unread"] == 1
    assert c.post(f"/notifications/{n['id']}/read").status_code == 204
    assert c.get("/notifications").json()["unread"] == 0


def test_low_risk_does_not_email(account, monkeypatch):
    c, _, _ = account
    sent = []

    async def fake_analyse(*args, **kwargs):
        return fake_result(30)

    async def fake_send(*args):
        sent.append(args)
        return True

    monkeypatch.setattr(scheduler, "analyse_trip", fake_analyse)
    monkeypatch.setattr(scheduler.mailer, "send", fake_send)
    trip_id = c.post("/trips", json=TRIP).json()["id"]
    assert c.post(f"/trips/{trip_id}/check").json()["high_risk"] is False
    assert sent == []


def test_trips_require_login(client):
    client.cookies.clear()
    assert client.get("/trips").status_code == 401
