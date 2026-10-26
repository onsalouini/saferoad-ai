import json

import pytest
from pydantic import ValidationError

from schemas import ChatInput
from services import assistant, overpass
from services.cache import TTLCache
from services.geo import sample_route, state_at


def test_state_detection():
    assert state_at(34.05, -118.24) == "CA"
    assert state_at(39.96, -83.0) == "OH"
    assert state_at(36.8, 10.18) is None  # Tunis


def test_sample_route_endpoints():
    geom = [[0.0, 0.0], [0.0, 1.0], [0.0, 2.0]]
    pts = sample_route(geom, 5)
    assert len(pts) == 5
    assert pts[0]["lng"] == pytest.approx(0) and pts[-1]["lng"] == pytest.approx(2)
    assert pts[-1]["km"] == pytest.approx(222.4, abs=1)


def test_overpass_classification():
    assert overpass._classify({"highway": "traffic_signals"}) == {"Traffic_Signal"}
    assert overpass._classify({"railway": "level_crossing"}) == {"Railway"}
    assert overpass._classify({"traffic_calming": "hump"}) == {"Traffic_Calming", "Bump"}
    assert overpass._classify({"junction": "roundabout"}) == {"Roundabout"}
    assert overpass._classify({"amenity": "bench"}) == set()


def test_overpass_query_covers_each_point():
    q = overpass._query([(1.0, 2.0), (3.0, 4.0)])
    assert q.count("around:") == 2  # une seule recherche spatiale par point
    assert '"junction"="roundabout"' in q and '"highway"="traffic_signals"' in q


def test_ttl_cache_expiry(monkeypatch):
    c = TTLCache(10, max_items=2)
    c.set("a", 1)
    assert c.get("a") == 1
    c.set("b", 2)
    c.set("c", 3)  # éjecte la plus ancienne
    assert c.get("a") is None and c.get("c") == 3


def test_chat_input_validation():
    ChatInput(messages=[{"role": "user", "content": "Bonjour"}])
    with pytest.raises(ValidationError):
        ChatInput(messages=[{"role": "assistant", "content": "x"}])
    with pytest.raises(ValidationError):
        ChatInput(messages=[{"role": "user", "content": "x"}], context={"x": "y" * 30000})


def test_assistant_disabled_without_key(account):
    c, _, _ = account
    assert c.get("/assistant/status").json()["available"] is False
    assert c.post("/assistant/chat", json={"messages": [{"role": "user", "content": "Bonjour"}]}).status_code == 503


def test_assistant_tools_schema():
    tools = {t.name: t.to_dict() for t in assistant._make_tools([])}
    assert set(tools) == {"analyser_trajet", "conditions_actuelles", "simuler_scenario"}
    assert tools["analyser_trajet"]["input_schema"]["required"] == ["depart", "arrivee"]


def test_ndjson_event():
    line = assistant._event("text", text="é")
    assert line.endswith("\n") and json.loads(line) == {"type": "text", "text": "é"}
