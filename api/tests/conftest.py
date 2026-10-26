"""Configuration des tests : base JSON temporaire, planificateur coupé, aucun service externe."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_DIR))

_tmp = tempfile.mkdtemp(prefix="saferoad-tests-")
os.environ.update({
    "LOCAL_DB_PATH": str(Path(_tmp) / "db.json"),
    "MONGO_URI": "",
    "SCHEDULER_ENABLED": "false",
    "JWT_SECRET": "secret-de-test-suffisamment-long-pour-hs256",
    "ANTHROPIC_API_KEY": "",
    "SMTP_HOST": "",
    "DISK_CACHE_PATH": str(Path(_tmp) / "cache.sqlite"),
    "VAPID_PRIVATE_KEY_FILE": str(Path(_tmp) / "vapid.pem"),
    "TOMTOM_API_KEY": "",
    "REDIS_URL": "",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def app():
    import main

    return main.app


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def model_ready():
    from ml.predict import model_service

    if not model_service.ready:
        pytest.skip("modèle absent (ml/models/saferoad_model.pkl non versionné)")
    return model_service


_n = 0


def _register(app_client):
    """Nouveau client connecté sur un compte neuf (cookies séparés)."""
    global _n
    _n += 1
    c = TestClient(app_client.app)
    r = c.post("/auth/register", json={"name": f"Votant {_n}", "email": f"votant{_n}@example.com", "password": "MotDePasse!123"})
    assert r.status_code == 201, r.text
    return c


@pytest.fixture()
def account(client):
    """Crée un compte et renvoie (client connecté par cookie, e-mail, mot de passe)."""
    global _n
    _n += 1
    email, password = f"user{_n}@example.com", "MotDePasse!123"
    r = client.post("/auth/register", json={"name": f"Utilisateur {_n}", "email": email, "password": password})
    assert r.status_code == 201, r.text
    return client, email, password
