# api/database.py
"""
Stockage des utilisateurs et de l'historique.

- MongoDB si la variable MONGO_URI est définie (fichier .env) ;
- sinon un fichier JSON local (api/data/local_db.json), pour lancer le projet sans configuration.
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
LOCAL_PATH = Path(__file__).resolve().parent / "data" / "local_db.json"


def _match(doc: dict, query: dict) -> bool:
    return all(doc.get(k) == v for k, v in query.items())


class LocalStore:
    """Mini base documentaire JSON (mono-processus), même interface que MongoStore."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = asyncio.Lock()
        self.data: dict[str, list[dict]] = {}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    async def insert(self, collection: str, doc: dict) -> str:
        async with self.lock:
            doc = {**doc, "_id": uuid.uuid4().hex}
            self.data.setdefault(collection, []).append(doc)
            self._save()
            return doc["_id"]

    async def find_one(self, collection: str, query: dict) -> dict | None:
        return next((d for d in self.data.get(collection, []) if _match(d, query)), None)

    async def find(self, collection: str, query: dict, limit: int = 50) -> list[dict]:
        docs = [d for d in self.data.get(collection, []) if _match(d, query)]
        docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
        return docs[:limit]

    async def delete(self, collection: str, query: dict) -> int:
        async with self.lock:
            before = self.data.get(collection, [])
            after = [d for d in before if not _match(d, query)]
            self.data[collection] = after
            self._save()
            return len(before) - len(after)


class MongoStore:
    def __init__(self, uri: str) -> None:
        from motor.motor_asyncio import AsyncIOMotorClient

        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[DB_NAME]

    async def insert(self, collection: str, doc: dict) -> str:
        doc = {**doc, "_id": uuid.uuid4().hex}
        await self.db[collection].insert_one(doc)
        return doc["_id"]

    async def find_one(self, collection: str, query: dict) -> dict | None:
        return await self.db[collection].find_one(query)

    async def find(self, collection: str, query: dict, limit: int = 50) -> list[dict]:
        cursor = self.db[collection].find(query).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def delete(self, collection: str, query: dict) -> int:
        res = await self.db[collection].delete_many(query)
        return res.deleted_count


class Database:
    store: LocalStore | MongoStore | None = None
    backend: str = "none"

    @classmethod
    async def connect(cls) -> None:
        if MONGO_URI:
            cls.store = MongoStore(MONGO_URI)
            await cls.store.db.command("ping")
            await cls.store.db["users"].create_index("email", unique=True)
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
