"""Background worker: renders templates, sends emails, records results."""
from __future__ import annotations

import logging
import traceback
from typing import Any

import anyio.to_thread

from resumehub.app.core import db
from resumehub.app.core.utils import utcnow

from .config import get_email_settings
from .mailer import send
from .renderer import render

log = logging.getLogger("hub.email_agent")


def _jobs():   return db.get_db()["email_jobs"]
def _emails(): return db.get_db()["email_log"]


async def _send_one(
    job_id: str,
    candidate: dict,
    role: dict,
    action: str,
    extra_ctx: dict,
) -> dict:
    """Send to one candidate; return a result record."""
    cfg = get_email_settings()

    name  = (candidate.get("resume") or {}).get("name") or "Candidate"
    email = _pick_email(candidate)

    result: dict[str, Any] = {
        "job_id":          job_id,
        "candidate_id":    candidate["_id"],
        "candidate_name":  name,
        "candidate_email": email,
        "action":          action,
        "role_id":         role.get("_id", ""),
        "task_id":         extra_ctx.get("task_id"),
        "sent_at":         utcnow(),
        "status":          "sent",
        "error":           None,
        "dry_run":         cfg.dry_run,
        "subject":         "",
    }

    ctx = {
        "candidate_name":  name,
        "candidate_email": email or "",
        "role_id":         role.get("_id", ""),
        "role":            role,
        "sender_name":     cfg.sender_name,
        "org_name":        cfg.org_name,
        **extra_ctx,
    }

    try:
        subject, body = render(action, ctx)
        result["subject"] = subject

        if not email:
            raise ValueError("No email address found for this candidate")

        if cfg.dry_run:
            log.info("[DRY RUN] would send '%s' → %s", subject, email)
        else:
            await anyio.to_thread.run_sync(
                lambda: send(cfg, to_addr=email, subject=subject, body=body)
            )
    except Exception as exc:  # noqa: BLE001
        result["status"] = "failed"
        result["error"]  = str(exc)[:500]
        log.error("email failed for %s: %s", candidate["_id"], exc)

    result["sent_at"] = utcnow()
    history_entry = {
        key: result[key]
        for key in ("job_id", "action", "role_id", "task_id", "sent_at", "status", "dry_run", "subject")
    }
    update: dict[str, Any] = {
        "$push": {"email_history": {"$each": [history_entry], "$sort": {"sent_at": 1}}}
    }
    if action == "rejected" and result["status"] == "sent" and not cfg.dry_run:
        update["$set"] = {"status": "rejected"}
    try:
        await db.resumes().update_one({"_id": candidate["_id"]}, update)
    except Exception:
        log.exception("could not update email history for %s", candidate["_id"])

    await _emails().insert_one(result)
    return result


def _pick_email(candidate: dict) -> str | None:
    # prefer the PII contact block; fall back to the email meta sender
    emails = (candidate.get("contact") or {}).get("emails", [])
    if emails:
        return emails[0]
    sender = (candidate.get("email") or {}).get("sender", "")
    # "Name <addr>" → "addr"
    if "<" in sender:
        return sender.split("<")[-1].rstrip(">").strip()
    return sender.strip() or None


async def execute_job(job_id: str) -> None:
    """Main background task invoked by the router."""
    jobs = _jobs()
    job  = await jobs.find_one({"_id": job_id})
    if not job:
        return

    await jobs.update_one({"_id": job_id}, {"$set": {"status": "running", "started_at": utcnow()}})

    cfg       = get_email_settings()
    action    = job["action"]
    role_id   = job.get("role_id", "")
    extra_ctx = job.get("extra_ctx", {})
    candidate_ids = job.get("candidate_ids", [])

    role = await db.job_roles().find_one({"_id": role_id}) or {} if role_id else {}

    results = {"sent": 0, "failed": 0, "skipped": 0}

    # cap at max_bulk
    candidate_ids = candidate_ids[: cfg.max_bulk]

    for cid in candidate_ids:
        candidate = await db.resumes().find_one({"_id": cid})
        if not candidate:
            results["skipped"] += 1
            continue
        rec = await _send_one(job_id, candidate, role, action, extra_ctx)
        if rec["status"] == "sent":
            results["sent"] += 1
        else:
            results["failed"] += 1

    await jobs.update_one(
        {"_id": job_id},
        {"$set": {"status": "done", "finished_at": utcnow(), "results": results}},
    )
    log.info("email job %s done: %s", job_id, results)
