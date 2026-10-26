# api/database.py
"""
Stockage des utilisateurs et de leurs données.

Schéma (aligné sur la collection Atlas `saferoad.users`) :
    {
      _id: ObjectId, full_name, email, password_hash (bcrypt),
      date_of_birth?, gender?, location?, phone?, created_at,
      reset_token_hash?, reset_expires?,
      history:       [ { id, kind, created_at, title, mode, risk_score, ... } ],
      saved_trips:   [ { id, origin, destination, mode, departure_time, days, tz, notify_email, last_alert_date } ],
      notifications: [ { id, created_at, trip_id, title, message, status, risk_score, read } ],
      push_subscriptions: [ { id, endpoint, keys, created_at } ],
      email_verified?, verify_token_hash?, assistant_usage?: { "AAAA-MM": {input_tokens, output_tokens, requests} }
    }

Collection partagée `reports` (signalements communautaires) :
    { id, user_id, type, comment, lat, lng, created_at, expires_at, confirmations, denials, voters }

Les listes intégrées au document sont manipulées par des opérations génériques
(push_item, list_items, update_item, pull_item, clear_items).

- MongoDB si la variable MONGO_URI est définie (fichier .env) ;
- sinon un fichier JSON local (api/data/local_db.json) au même schéma,
  pour lancer le projet sans configuration.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB", "saferoad")
LOCAL_PATH = Path(os.getenv("LOCAL_DB_PATH", Path(__file__).resolve().parent / "data" / "local_db.json"))
LIST_FIELDS = ("history", "saved_trips", "notifications", "push_subscriptions")
LIST_MAX = {"history": 200, "saved_trips": 20, "notifications": 100, "push_subscriptions": 10}  # par utilisateur


class DuplicateEmail(Exception):
    pass


def _sorted(items: list[dict], limit: int) -> list[dict]:
    return sorted(items, key=lambda h: str(h.get("created_at", "")), reverse=True)[:limit]


class LocalStore:
    """Mini base JSON mono-processus, même interface que MongoStore."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = asyncio.Lock()
        self.users: list[dict] = []
        self.reports: list[dict] = []
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.users, self.reports = data.get("users", []), data.get("reports", [])

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"users": self.users, "reports": self.reports}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        tmp.replace(self.path)

    def _find(self, user_id: str) -> dict | None:
        return next((u for u in self.users if u["_id"] == user_id), None)

    # ------------------------------------------------------------ utilisateurs
    async def create_user(self, doc: dict) -> str:
        async with self.lock:
            if any(u.get("email") == doc["email"] for u in self.users):
                raise DuplicateEmail
            doc = {**doc, "_id": uuid.uuid4().hex, **{f: [] for f in LIST_FIELDS}}
            self.users.append(doc)
            self._save()
            return doc["_id"]

    async def get_user(self, user_id: str) -> dict | None:
        return self._find(user_id)

    async def get_user_by_email(self, email: str) -> dict | None:
        return next((u for u in self.users if u.get("email") == email), None)

    async def get_user_by_field(self, field: str, value) -> dict | None:
        return next((u for u in self.users if u.get(field) == value), None)

    async def update_user(self, user_id: str, fields: dict) -> None:
        async with self.lock:
            user = self._find(user_id)
            if user is not None:
                for k, v in fields.items():
                    if v is None:
                        user.pop(k, None)
                    else:
                        user[k] = v
                self._save()

    async def users_with(self, field: str) -> list[dict]:
        return [u for u in self.users if u.get(field)]

    async def increment(self, user_id: str, path: list[str], values: dict[str, int]) -> None:
        async with self.lock:
            node = self._find(user_id)
            if node is None:
                return
            for key in path:
                node = node.setdefault(key, {})
            for k, v in values.items():
                node[k] = node.get(k, 0) + v
            self._save()

    async def delete_user(self, user_id: str) -> None:
        async with self.lock:
            self.users = [u for u in self.users if u["_id"] != user_id]
            for r in self.reports:
                if r.get("user_id") == user_id:
                    r["user_id"] = None  # le signalement reste utile aux autres, anonymisé
            self._save()

    # ------------------------------------------------------------ signalements
    async def add_report(self, doc: dict) -> None:
        async with self.lock:
            now = doc["created_at"]
            self.reports = [r for r in self.reports if r["expires_at"] > now][-5000:] + [doc]
            self._save()

    async def list_reports(self, bbox: tuple[float, float, float, float], now: str) -> list[dict]:
        s, w, n, e = bbox
        return [r for r in self.reports if r["expires_at"] > now and s <= r["lat"] <= n and w <= r["lng"] <= e]

    async def get_report(self, report_id: str) -> dict | None:
        return next((r for r in self.reports if r["id"] == report_id), None)

    async def update_report(self, report_id: str, fields: dict) -> None:
        async with self.lock:
            r = next((r for r in self.reports if r["id"] == report_id), None)
            if r:
                r.update(fields)
                self._save()

    # ---------------------------------------------------------- listes intégrées
    async def push_item(self, user_id: str, field: str, entry: dict) -> None:
        async with self.lock:
            user = self._find(user_id)
            if user is not None:
                user[field] = (user.get(field) or []) + [entry]
                user[field] = user[field][-LIST_MAX[field]:]
                self._save()

    async def list_items(self, user_id: str, field: str, limit: int = 200) -> list[dict]:
        user = self._find(user_id) or {}
        return _sorted(user.get(field) or [], limit)

    async def update_item(self, user_id: str, field: str, item_id: str, fields: dict) -> bool:
        async with self.lock:
            user = self._find(user_id) or {}
            for item in user.get(field) or []:
                if item.get("id") == item_id:
                    item.update(fields)
                    self._save()
                    return True
            return False

    async def update_all_items(self, user_id: str, field: str, fields: dict) -> None:
        async with self.lock:
            user = self._find(user_id) or {}
            for item in user.get(field) or []:
                item.update(fields)
            self._save()

    async def pull_item(self, user_id: str, field: str, item_id: str) -> bool:
        async with self.lock:
            user = self._find(user_id)
            if not user:
                return False
            before = len(user.get(field) or [])
            user[field] = [h for h in user.get(field) or [] if h.get("id") != item_id]
            self._save()
            return len(user[field]) < before

    async def clear_items(self, user_id: str, field: str) -> None:
        async with self.lock:
            user = self._find(user_id)
            if user:
                user[field] = []
                self._save()


class MongoStore:
    # Champs volumineux exclus quand on charge l'utilisateur à chaque requête authentifiée
    LIGHT = {"history": 0, "notifications": 0}

    def __init__(self, uri: str) -> None:
        from motor.motor_asyncio import AsyncIOMotorClient

        self.client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=8000)
        self.db = self.client[DB_NAME]
        self.users = self.db["users"]
        self.reports = self.db["reports"]

    @staticmethod
    def _oid(user_id: str):
        from bson import ObjectId
        from bson.errors import InvalidId

        try:
            return ObjectId(user_id)
        except (InvalidId, TypeError):
            return user_id

    @staticmethod
    def _out(doc: dict | None) -> dict | None:
        if doc is not None:
            doc["_id"] = str(doc["_id"])
        return doc

    # ------------------------------------------------------------ utilisateurs
    async def create_user(self, doc: dict) -> str:
        from pymongo.errors import DuplicateKeyError

        try:
            res = await self.users.insert_one({**doc, **{f: [] for f in LIST_FIELDS}})
        except DuplicateKeyError:
            raise DuplicateEmail
        return str(res.inserted_id)

    async def get_user(self, user_id: str) -> dict | None:
        return self._out(await self.users.find_one({"_id": self._oid(user_id)}, self.LIGHT))

    async def get_user_by_email(self, email: str) -> dict | None:
        return self._out(await self.users.find_one({"email": email}, self.LIGHT))

    async def get_user_by_field(self, field: str, value) -> dict | None:
        return self._out(await self.users.find_one({field: value}, self.LIGHT))

    async def update_user(self, user_id: str, fields: dict) -> None:
        sets = {k: v for k, v in fields.items() if v is not None}
        unsets = {k: "" for k, v in fields.items() if v is None}
        update = {**({"$set": sets} if sets else {}), **({"$unset": unsets} if unsets else {})}
        if update:
            await self.users.update_one({"_id": self._oid(user_id)}, update)

    async def users_with(self, field: str) -> list[dict]:
        cursor = self.users.find({f"{field}.0": {"$exists": True}}, self.LIGHT)
        return [self._out(d) async for d in cursor]

    async def increment(self, user_id: str, path: list[str], values: dict[str, int]) -> None:
        prefix = ".".join(path)
        await self.users.update_one({"_id": self._oid(user_id)}, {"$inc": {f"{prefix}.{k}": v for k, v in values.items()}})

    async def delete_user(self, user_id: str) -> None:
        await self.users.delete_one({"_id": self._oid(user_id)})
        await self.reports.update_many({"user_id": user_id}, {"$set": {"user_id": None}})

    # ------------------------------------------------------------ signalements
    async def add_report(self, doc: dict) -> None:
        await self.reports.insert_one({**doc, "_id": doc["id"]})

    async def list_reports(self, bbox: tuple[float, float, float, float], now: str) -> list[dict]:
        s, w, n, e = bbox
        cursor = self.reports.find({"expires_at": {"$gt": now}, "lat": {"$gte": s, "$lte": n},
                                    "lng": {"$gte": w, "$lte": e}}, {"_id": 0}).limit(500)
        return [d async for d in cursor]

    async def get_report(self, report_id: str) -> dict | None:
        return await self.reports.find_one({"_id": report_id}, {"_id": 0})

    async def update_report(self, report_id: str, fields: dict) -> None:
        await self.reports.update_one({"_id": report_id}, {"$set": fields})

    # ---------------------------------------------------------- listes intégrées
    async def push_item(self, user_id: str, field: str, entry: dict) -> None:
        await self.users.update_one(
            {"_id": self._oid(user_id)},
            {"$push": {field: {"$each": [entry], "$slice": -LIST_MAX[field]}}},
        )

    async def list_items(self, user_id: str, field: str, limit: int = 200) -> list[dict]:
        user = await self.users.find_one({"_id": self._oid(user_id)}, {field: 1})
        return _sorted((user or {}).get(field) or [], limit)

    async def update_item(self, user_id: str, field: str, item_id: str, fields: dict) -> bool:
        res = await self.users.update_one(
            {"_id": self._oid(user_id), f"{field}.id": item_id},
            {"$set": {f"{field}.$.{k}": v for k, v in fields.items()}},
        )
        return res.matched_count > 0

    async def update_all_items(self, user_id: str, field: str, fields: dict) -> None:
        await self.users.update_one(
            {"_id": self._oid(user_id)},
            {"$set": {f"{field}.$[].{k}": v for k, v in fields.items()}},
        )

    async def pull_item(self, user_id: str, field: str, item_id: str) -> bool:
        res = await self.users.update_one({"_id": self._oid(user_id)}, {"$pull": {field: {"id": item_id}}})
        return res.modified_count > 0

    async def clear_items(self, user_id: str, field: str) -> None:
        await self.users.update_one({"_id": self._oid(user_id)}, {"$set": {field: []}})


class Database:
    store: LocalStore | MongoStore | None = None
    backend: str = "none"

    @classmethod
    async def connect(cls) -> None:
        if MONGO_URI:
            cls.store = MongoStore(MONGO_URI)
            await cls.store.db.command("ping")
            # index unique sur l'e-mail (ignoré s'il existe déjà ou si des doublons l'empêchent)
            try:
                await cls.store.users.create_index("email", unique=True)
                await cls.store.users.create_index("reset_token_hash", sparse=True)
                await cls.store.users.create_index("verify_token_hash", sparse=True)
                await cls.store.reports.create_index([("lat", 1), ("lng", 1)])
                await cls.store.reports.create_index("expires_at")  # dates ISO : filtrées à la lecture
            except Exception as e:  # noqa: BLE001
                print(f"Index non cree : {e}")
            cls.backend = "mongodb"
        else:
            cls.store = LocalStore(LOCAL_PATH)
            cls.backend = "local-json"
        print(f"Base de donnees : {cls.backend}")

    @classmethod
    async def disconnect(cls) -> None:
        if isinstance(cls.store, MongoStore):
            cls.store.client.close()


def db() -> LocalStore | MongoStore:
    if Database.store is None:
        raise RuntimeError("Base de données non initialisée")
    return Database.store


def new_id() -> str:
    return uuid.uuid4().hex
