# api/services/push.py
"""
Notifications Web Push (standard VAPID) : les alertes arrivent même quand l'application est fermée.

Les clés VAPID sont lues depuis VAPID_PRIVATE_KEY_FILE ; sinon elles sont générées au premier
démarrage dans api/data/vapid_private.pem (à conserver : changer de clé invalide les abonnements).
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path

from database import db

KEY_FILE = Path(os.getenv("VAPID_PRIVATE_KEY_FILE", Path(__file__).resolve().parents[1] / "data" / "vapid_private.pem"))
CONTACT = os.getenv("VAPID_CONTACT", "mailto:admin@example.com")
_public_key: str | None = None


def _load():
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from py_vapid import Vapid01

    if KEY_FILE.exists():
        v = Vapid01.from_file(str(KEY_FILE))
    else:
        v = Vapid01()
        v.generate_keys()
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        v.save_key(str(KEY_FILE))
        print(f"Clés VAPID générées : {KEY_FILE}")
    raw = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def public_key() -> str | None:
    global _public_key
    if _public_key is None:
        try:
            _public_key = _load()
        except Exception as e:  # noqa: BLE001 - dépendance absente ou clé illisible : push désactivé
            print(f"Web Push désactivé : {e}")
            return None
    return _public_key


def _send_one(sub: dict, payload: str) -> int:
    from pywebpush import WebPushException, webpush

    try:
        webpush(subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]}, data=payload,
                vapid_private_key=str(KEY_FILE), vapid_claims={"sub": CONTACT}, ttl=3600)
        return 201
    except WebPushException as e:
        return e.response.status_code if e.response is not None else 500


async def notify(user: dict, title: str, body: str, url: str = "/mes-trajets") -> int:
    """Envoie à tous les appareils abonnés ; supprime les abonnements expirés. Renvoie le nombre d'envois réussis."""
    if not public_key():
        return 0
    subs = await db().list_items(user["_id"], "push_subscriptions")
    payload = json.dumps({"title": title, "body": body, "url": url}, ensure_ascii=False)
    ok = 0
    for sub in subs:
        status = await asyncio.to_thread(_send_one, sub, payload)
        if status in (404, 410):  # abonnement révoqué par le navigateur
            await db().pull_item(user["_id"], "push_subscriptions", sub["id"])
        elif status < 300:
            ok += 1
    return ok
