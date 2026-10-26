# api/services/diskcache.py
"""
Cache persistant (SQLite, bibliothèque standard) pour les données lentes à obtenir et qui changent
peu : équipements routiers OpenStreetMap, aires de repos. Survit aux redémarrages de l'API, ce qui
évite de réinterroger Overpass (souvent saturé) pour les itinéraires déjà vus.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

PATH = Path(os.getenv("DISK_CACHE_PATH", Path(__file__).resolve().parents[1] / "data" / "cache.sqlite"))
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(PATH, check_same_thread=False)
        _conn.execute("CREATE TABLE IF NOT EXISTS cache (k TEXT PRIMARY KEY, v TEXT, expires REAL)")
    return _conn


def get_many(keys: list[str]) -> dict[str, object]:
    if not keys:
        return {}
    now = time.time()
    out = {}
    with _lock:
        db = _db()
        for i in range(0, len(keys), 500):
            chunk = keys[i:i + 500]
            rows = db.execute(f"SELECT k, v, expires FROM cache WHERE k IN ({','.join('?' * len(chunk))})", chunk)
            out.update({k: json.loads(v) for k, v, exp in rows if exp > now})
    return out


def set_many(items: dict[str, object], ttl_s: float) -> None:
    if not items:
        return
    exp = time.time() + ttl_s
    with _lock:
        db = _db()
        db.executemany("INSERT OR REPLACE INTO cache (k, v, expires) VALUES (?, ?, ?)",
                       [(k, json.dumps(v, ensure_ascii=False), exp) for k, v in items.items()])
        db.commit()
