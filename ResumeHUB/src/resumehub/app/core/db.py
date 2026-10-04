from __future__ import annotations

from typing import TYPE_CHECKING

from pymongo import AsyncMongoClient

from .config import Settings, get_settings

if TYPE_CHECKING:  # pragma: no cover
    from pymongo.asynchronous.collection import AsyncCollection
    from pymongo.asynchronous.database import AsyncDatabase

USERS = "users"
ACCESS_ROLES = "access_roles"
AUDIT = "audit_log"
MATCH_JOBS = "match_jobs"


class _Mongo:
    client: AsyncMongoClient | None = None
    db: "AsyncDatabase | None" = None


_mongo = _Mongo()


async def connect(settings: Settings) -> "AsyncDatabase":
    _mongo.client = AsyncMongoClient(
        settings.mongo_uri, tz_aware=True, serverSelectionTimeoutMS=5000
    )
    _mongo.db = _mongo.client[settings.mongo_db]
    await _mongo.client.admin.command("ping")
    return _mongo.db


async def disconnect() -> None:
    if _mongo.client is not None:
        await _mongo.client.close()
    _mongo.client = None
    _mongo.db = None


def get_db() -> "AsyncDatabase":
    if _mongo.db is None:
        raise RuntimeError("database is not connected")
    return _mongo.db


def resumes() -> "AsyncCollection":
    return get_db()[get_settings().resume_collection]


def job_roles() -> "AsyncCollection":
    return get_db()[get_settings().role_collection]


def users() -> "AsyncCollection":
    return get_db()[USERS]


def access_roles() -> "AsyncCollection":
    return get_db()[ACCESS_ROLES]


def audit_log() -> "AsyncCollection":
    return get_db()[AUDIT]


def match_jobs() -> "AsyncCollection":
    return get_db()[MATCH_JOBS]
