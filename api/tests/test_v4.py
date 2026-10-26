from datetime import datetime, timezone

import pytest

from ml.features import build_row, road_class
from services import profiles, sun
from services.trip import _pauses


@pytest.mark.parametrize("name,expected", [
    ("I-95 N", "freeway"), ("Golden State Fwy S", "freeway"), ("Interstate 70", "freeway"), ("I 70", "freeway"),
    ("US-101 N", "highway"), ("CA-91 W", "highway"), ("Highway 17", "highway"), ("US 23;OH 3", "highway"),
    ("Main St", "local"), ("Westheimer Rd", "local"), ("Indiana Ave", "local"), (None, "local"),
])
def test_road_class(name, expected):
    assert road_class(name) == expected


def test_road_class_in_row():
    assert build_row({"Street": "I-5 N"})["Road_Freeway"] == 1
    assert build_row({"Road_Class": "highway"})["Road_Highway"] == 1
    row = build_row({})
    assert row["Road_Freeway"] == row["Road_Highway"] == 0


def test_solar_position_noon_and_night():
    # Columbus (OH), 21 juin, midi solaire ≈ 17:30 UTC : soleil haut au sud
    el, az = sun.solar_position(39.96, -83.0, datetime(2026, 6, 21, 17, 30, tzinfo=timezone.utc))
    assert 70 < el < 75 and 160 < az < 200
    el, _ = sun.solar_position(39.96, -83.0, datetime(2026, 6, 21, 5, 0, tzinfo=timezone.utc))
    assert el < 0


def test_glare_when_driving_into_low_sun():
    # Coucher de soleil vers l'ouest-nord-ouest en juin : rouler vers l'ouest éblouit, vers l'est non
    t, off = "2026-06-21T20:30", -4 * 3600  # heure locale EDT
    assert sun.glare(39.96, -83.0, 295, t, off) is not None
    assert sun.glare(39.96, -83.0, 115, t, off) is None


def test_bearing():
    assert sun.bearing([0, 0], [0, 1]) == pytest.approx(90, abs=0.5)
    assert sun.bearing([0, 0], [1, 0]) == pytest.approx(0, abs=0.5)


def test_profiles_lower_threshold_and_check_wind():
    assert profiles.threshold(0.51, "moto") == pytest.approx(0.41)
    assert profiles.threshold(0.51, "standard") == 0.51
    seg = [{"weather": {"Wind_Speed_mph": 40, "Temperature_F": 30}}]
    msgs = profiles.checks("moto", seg)
    assert any("Vent fort" in m for m in msgs) and any("verglas" in m for m in msgs)
    assert profiles.checks("standard", seg) == []


def test_pauses_every_two_hours():
    route = {"duration_min": 300, "geometry": [[0, i / 10] for i in range(101)]}
    p = _pauses(route, 120)
    assert [x["after_min"] for x in p] == [120, 240]
    assert _pauses({"duration_min": 90, "geometry": route["geometry"]}, 120) == []


def test_reports_lifecycle(account, client):
    c, _, _ = account
    r = c.post("/reports", json={"type": "nid_de_poule", "lat": 39.9, "lng": -83.0, "comment": "voie de droite"})
    assert r.status_code == 201 and r.json()["mine"]
    rid = r.json()["id"]
    found = client.get("/reports", params={"south": 39.8, "west": -83.1, "north": 40.0, "east": -82.9}).json()
    assert rid in [x["id"] for x in found]
    assert "user_id" not in found[0] and "voters" not in found[0]
    assert c.post(f"/reports/{rid}/vote", json={"still_there": True}).status_code == 409  # auteur a déjà voté
    assert c.post("/reports", json={"type": "inconnu", "lat": 0, "lng": 0}).status_code == 422


def test_report_removed_after_three_denials(client):
    from tests.conftest import _register

    owner = _register(client)
    rid = owner.post("/reports", json={"type": "accident", "lat": 40.5, "lng": -80.0}).json()["id"]
    for _ in range(3):
        voter = _register(client)
        assert voter.post(f"/reports/{rid}/vote", json={"still_there": False}).status_code == 200
    found = client.get("/reports", params={"south": 40.4, "west": -80.1, "north": 40.6, "east": -79.9}).json()
    assert rid not in [x["id"] for x in found]


def test_verify_email(client, monkeypatch):
    from routes import account
    from tests.conftest import _register

    sent = {}

    async def fake_send(to, subject, text):
        sent["text"] = text
        return True

    monkeypatch.setattr(account.mailer, "send", fake_send)
    c = _register(client)
    assert c.get("/auth/me").json()["email_verified"] is False
    token = sent["text"].split("token=")[1].split()[0]
    assert c.post("/auth/verify", json={"token": token}).status_code == 200
    assert c.get("/auth/me").json()["email_verified"] is True
    assert c.post("/auth/verify", json={"token": token}).status_code == 400


def test_export_and_delete_account(account):
    c, email, password = account
    data = c.get("/account/export")
    assert data.status_code == 200 and "attachment" in data.headers["content-disposition"]
    body = data.json()
    assert body["email"] == email and "password_hash" not in body
    assert c.post("/account/delete", json={"password": "mauvais"}).status_code == 403
    assert c.post("/account/delete", json={"password": password}).status_code == 204
    assert c.post("/auth/login", json={"email": email, "password": password}).status_code == 401


def test_push_public_key(client):
    r = client.get("/push/public-key")
    assert r.status_code == 200 and len(r.json()["public_key"]) > 80
