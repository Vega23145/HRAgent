"""Where the structured JSON lives. MongoDB, or plain files when MONGO_URI is unset."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

from .config import Config


class Store(Protocol):
    def has(self, key: str) -> bool: ...
    def save(self, key: str, record: dict) -> None: ...  # idempotent upsert
    def keys(self) -> set[str]: ...
    def close(self) -> None: ...


class MongoStore:
    """One document per resume. _id IS the key, so the same mail can never create
    a second document, and the file <key>.<ext> is findable from the doc and back."""

    def __init__(self, collection, client=None):
        self._col, self._client = collection, client

    @classmethod
    def connect(cls, uri: str, db: str, collection: str) -> "MongoStore":
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")  # fail fast with a clear error, not mid-run
        return cls(client[db][collection], client)

    def has(self, key: str) -> bool:
        return self._col.find_one({"_id": key}, {"_id": 1}) is not None

    def save(self, key: str, record: dict) -> None:
        self._col.replace_one({"_id": key}, {"_id": key, **record}, upsert=True)

    def keys(self) -> set[str]:
        return {d["_id"] for d in self._col.find({}, {"_id": 1})}

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


class JsonDirStore:
    """Fallback without MongoDB: OUT_DIR/<key>.json"""

    def __init__(self, directory: Path):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)

    def has(self, key: str) -> bool:
        return (self.dir / f"{key}.json").is_file()

    def save(self, key: str, record: dict) -> None:
        tmp = self.dir / f"{key}.json.tmp"
        tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False))
        os.replace(tmp, self.dir / f"{key}.json")

    def keys(self) -> set[str]:
        return {p.stem for p in self.dir.glob("*.json")}

    def close(self) -> None:
        pass


def build_store(cfg: Config) -> Store:
    if cfg.mongo_uri:
        return MongoStore.connect(cfg.mongo_uri, cfg.mongo_db, cfg.mongo_collection)
    return JsonDirStore(Path(cfg.out_dir))
