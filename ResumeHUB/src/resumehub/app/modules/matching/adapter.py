"""Thin adapter over the external ``resume_matcher`` package.

The matcher is synchronous and keeps its own Mongo handles (``connect(cfg)``), configured
through its own environment (``Config.from_env()``). Calls here are blocking: routers run
them in a worker thread. The import is lazy so the API still boots without the package.
"""
from __future__ import annotations

import threading
from types import SimpleNamespace

_lock = threading.Lock()
_state: SimpleNamespace | None = None


class MatcherUnavailable(RuntimeError):
    pass


def _load() -> SimpleNamespace:
    global _state
    with _lock:
        if _state is None:
            try:
                from resumehub.app.role_engine.resume_matcher.config import Config
                from resumehub.app.role_engine.resume_matcher.db import connect
                from resumehub.app.role_engine.resume_matcher.runner import match_all, match_one, match_role
            except ImportError as e:
                raise MatcherUnavailable(f"resume_matcher is not installed: {e}") from e
            try:
                resume_db, role_db = connect(Config.from_env())
            except Exception as e:  # noqa: BLE001
                raise MatcherUnavailable(f"resume_matcher could not connect: {e}") from e
            _state = SimpleNamespace(
                resume_db=resume_db, role_db=role_db,
                match_one=match_one, match_role=match_role, match_all=match_all,
            )
        return _state


def run_one(resume_id: str, role_id: str):
    s = _load()
    return s.match_one(resume_id, role_id, s.resume_db, s.role_db)


def run_role(role_id: str):
    s = _load()
    return s.match_role(role_id, s.resume_db, s.role_db)


def run_all():
    s = _load()
    return s.match_all(s.resume_db, s.role_db)


def available() -> bool:
    try:
        _load()
        return True
    except MatcherUnavailable:
        return False
