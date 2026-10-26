import time

from auth import COOKIE_NAME


def test_register_sets_httponly_cookie(client):
    r = client.post("/auth/register", json={"name": "Alice", "email": "Alice@Example.com", "password": "MotDePasse!123"})
    assert r.status_code == 201
    assert "httponly" in r.headers["set-cookie"].lower()
    assert r.json()["user"]["email"] == "alice@example.com"
    me = client.get("/auth/me")
    assert me.status_code == 200 and me.json()["name"] == "Alice"


def test_duplicate_email(client, account):
    _, email, _ = account
    r = client.post("/auth/register", json={"name": "Bis", "email": email, "password": "MotDePasse!123"})
    assert r.status_code == 409


def test_password_longer_than_bcrypt_limit_is_rejected(client):
    r = client.post("/auth/register", json={"name": "Long", "email": "long@example.com", "password": "a" * 80})
    assert r.status_code == 422


def test_login_logout(client, account):
    c, email, password = account
    c.post("/auth/logout")
    assert c.get("/auth/me").status_code == 401
    r = c.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    assert c.get("/auth/me").status_code == 200


def test_bearer_token_still_accepted(client, account):
    c, email, password = account
    token = c.post("/auth/login", json={"email": email, "password": password}).json()["token"]
    c.cookies.clear()
    assert c.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_login_rate_limited_per_email(client, account):
    c, email, _ = account
    codes = [c.post("/auth/login", json={"email": email, "password": "mauvais"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429


def test_forgot_and_reset_password(client, account, monkeypatch):
    c, email, _ = account
    sent = {}

    async def fake_send(to, subject, text):
        sent.update(to=to, text=text)
        return True

    from services import mailer
    monkeypatch.setattr(mailer, "send", fake_send)

    old_cookie = c.cookies.get(COOKIE_NAME)
    assert c.post("/auth/forgot", json={"email": email}).status_code == 202
    assert sent["to"] == email
    token = sent["text"].split("token=")[1].split()[0]

    # Même réponse pour un compte inexistant (pas de fuite d'information)
    assert c.post("/auth/forgot", json={"email": "inconnu@example.com"}).status_code == 202

    assert c.post("/auth/reset", json={"token": "x" * 30, "password": "Nouveau!12345"}).status_code == 400
    time.sleep(1.1)  # la session précédente doit être antérieure au changement
    r = c.post("/auth/reset", json={"token": token, "password": "Nouveau!12345"})
    assert r.status_code == 200
    assert c.post("/auth/reset", json={"token": token, "password": "Autre!123456"}).status_code == 400  # usage unique

    c.cookies.clear()
    c.cookies.set(COOKIE_NAME, old_cookie)
    assert c.get("/auth/me").status_code == 401  # ancienne session révoquée
    c.cookies.clear()
    assert c.post("/auth/login", json={"email": email, "password": "Nouveau!12345"}).status_code == 200
