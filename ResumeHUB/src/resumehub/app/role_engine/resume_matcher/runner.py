"""
Core matching logic — no I/O; everything injected.

Three entry points:

    match_one(resume_key, role_id, resume_db, role_db)
        Score one resume against one role.

    match_role(role_id, resume_db, role_db, skip_existing)
        Score every resume against one role.

    match_all(resume_db, role_db, skip_existing)
        Score every resume against every role.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .algo import match
from .db import ResumeDB, RoleDB

log = logging.getLogger(__name__)


@dataclass
class RunStats:
    matched: int = 0
    skipped: int = 0
    errors: int = 0


def match_one(
    resume_key: str,
    role_id: str,
    resume_db: ResumeDB,
    role_db: RoleDB,
    overwrite: bool = True,
) -> dict | None:
    """
    Score a single resume against a single role.
    Returns the result dict, or None if either document is missing.
    """
    role_doc = role_db.get(role_id)
    if role_doc is None:
        log.error("role not found: %s", role_id)
        return None

    resume_doc = resume_db.get(resume_key)
    if resume_doc is None:
        log.error("resume not found: %s", resume_key)
        return None

    if not overwrite and f"match.{role_id}" in (resume_doc.get("match") or {}):
        log.debug("skip existing: %s x %s", resume_key, role_id)
        return resume_doc["match"][role_id]

    role = role_db.to_role(role_doc)
    result = match(role, resume_doc).to_dict()
    resume_db.save_result(resume_key, role_id, result)
    log.info("matched %s x %s -> %.1f", resume_key, role_id, result["score"])
    return result


def match_role(
    role_id: str,
    resume_db: ResumeDB,
    role_db: RoleDB,
    skip_existing: bool = True,
) -> RunStats:
    """Score all resumes against one role."""
    role_doc = role_db.get(role_id)
    if role_doc is None:
        log.error("role not found: %s", role_id)
        return RunStats(errors=1)

    if skip_existing:
        keys = resume_db.find_unmatched(role_id)
    else:
        keys = resume_db.all_keys()

    try:
        role = role_db.to_role(role_doc)
    except Exception:
        log.exception("cannot build role object for %s", role_id)
        return RunStats(errors=1)

    stats = RunStats()
    for key in keys:
        try:
            resume_doc = resume_db.get(key)
            if resume_doc is None:
                stats.errors += 1
                continue
            result = match(role, resume_doc).to_dict()
            resume_db.save_result(key, role_id, result)
            log.info("matched %s x %s -> %.1f", key, role_id, result["score"])
            stats.matched += 1
        except Exception:
            log.exception("error matching %s x %s", key, role_id)
            stats.errors += 1

    return stats


def match_all(
    resume_db: ResumeDB,
    role_db: RoleDB,
    skip_existing: bool = True,
) -> dict[str, RunStats]:
    """Score every resume against every role. Returns {role_id: RunStats}."""
    stats: dict[str, RunStats] = {}
    for role_id in role_db.all_ids():
        log.info("processing role: %s", role_id)
        stats[role_id] = match_role(role_id, resume_db, role_db, skip_existing)
    return stats
