"""Permission strings look like ``resource:action``.

Wildcards: ``*`` (everything), ``resumes:*`` (every action on a resource),
``*:read`` (one action on every resource). A *deny* always beats an *allow*.
"""
from __future__ import annotations

import re
from typing import Iterable

PERM_PATTERN = r"^(\*|(\*|[a-z][a-z0-9_]*):(\*|[a-z][a-z0-9_]*))$"
PERM_RE = re.compile(PERM_PATTERN)


def covers(granted: str, required: str) -> bool:
    """True if the ``granted`` pattern covers the ``required`` permission."""
    if granted == "*":
        return True
    g_res, _, g_act = granted.partition(":")
    r_res, _, r_act = required.partition(":")
    return g_res in ("*", r_res) and g_act in ("*", r_act)


def is_allowed(required: str, allow: Iterable[str], deny: Iterable[str]) -> bool:
    if any(covers(d, required) for d in deny):
        return False
    return any(covers(a, required) for a in allow)


def effective(catalog: Iterable[str], allow: Iterable[str], deny: Iterable[str]) -> list[str]:
    allow, deny = list(allow), list(deny)
    return sorted(p for p in catalog if is_allowed(p, allow, deny))
