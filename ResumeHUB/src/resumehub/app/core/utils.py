from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from typing import Any

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{1,62}$"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def clean_keys(obj: Any, depth: int = 0, max_depth: int = 10) -> None:
    """Reject Mongo operator / dotted keys anywhere in user-supplied JSON."""
    if depth > max_depth:
        raise ValueError("document is nested too deeply")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str) or k.startswith("$") or "." in k or "\0" in k:
                raise ValueError(f"illegal key: {k!r}")
            clean_keys(v, depth + 1, max_depth)
    elif isinstance(obj, list):
        for v in obj:
            clean_keys(v, depth + 1, max_depth)


def deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and v and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def build_set(existing: Any, patch: dict, prefix: str = "") -> dict:
    """Turn a nested patch into dotted ``$set`` paths.

    Dicts are descended into only where the stored value is also a dict, so we never
    ask Mongo to create a child field inside a null/scalar parent.
    """
    out: dict[str, Any] = {}
    for k, v in patch.items():
        cur = existing.get(k) if isinstance(existing, dict) else None
        if isinstance(v, dict) and v and isinstance(cur, dict):
            out.update(build_set(cur, v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


def jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        obj = dataclasses.asdict(obj)
    elif hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    return json.loads(json.dumps(obj, default=str))
