"""
One email in -> one JSON record + one resume file out, linked by the same key:

    store record  _id = <key>                 (MongoDB document, or OUT_DIR/<key>.json)
    resume file   <RESUME_DIR>/<key>.<ext>

Write order is what prevents orphans:
    1. extract (Gemini)           nothing persisted yet, failure leaves no trace
    2. write the resume file      atomic rename
    3. save the record            if this fails the file is deleted again
A crash between 2 and 3 leaves one orphan file, which reconcile() sweeps.

Stdlib only; extractor/store/files are injected, so the flow is testable offline.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .config import MAX_TEXT_CHARS, MIN_TEXT_CHARS
from .email import send_rejection
from .files import ResumeFiles
from .matching import RoleMatcher
from .mail import parse_mail
from .reader import _ocr_pdf, read_text
from .store import Store
from .textprep import prepare

log = logging.getLogger(__name__)

# text -> (resume dict, meta dict). meta is logged, never stored.
Extractor = Callable[[str], tuple[dict, dict]]


class NoTextError(Exception):
    """Attachment has no usable text layer (scanned PDF?)."""


def make_key(message_id: str, filename: str) -> str:
    return hashlib.sha256(f"{message_id}:{filename}".encode()).hexdigest()[:16]


def _all_role_scores_below(matches: dict, threshold: float) -> bool:
    scores = [result.get("score") for result in matches.values() if isinstance(result, dict)]
    return bool(scores) and len(scores) == len(matches) and all(
        isinstance(score, (int, float)) and score < threshold for score in scores
    )


def _send_rejection_if_needed(
    key: str,
    record: dict,
    store: Store,
    cfg,
    email_sender,
) -> None:
    threshold = cfg.auto_reject_score_threshold
    if threshold is None or not _all_role_scores_below(record.get("match", {}), threshold):
        return

    delivery = record.get("rejection_email", {})
    if delivery.get("status") in {"sent", "skipped", "dry_run"}:
        _persist_rejection_log(key, record, store)
        return

    emails = record.get("contact", {}).get("emails", [])
    if not emails:
        record["rejection_email"] = {"status": "skipped", "reason": "no_candidate_email"}
        store.save(key, record)
        log.warning("cannot send rejection for %s: no candidate email found", key)
        return

    if delivery.get("status") != "pending":
        record["rejection_email"] = {"status": "pending"}
        store.save(key, record)

    role_scores = [
        {
            "title": role_id.replace("-", " ").replace("_", " ").title(),
            "score": f"{result['score']:.1f}",
        }
        for role_id, result in record["match"].items()
    ]
    reason = (
        f"Your resume scored below the minimum match score of {threshold:g} "
        "for every role we reviewed."
    )
    send_result = email_sender(
        cfg,
        to_addr=emails[0],
        candidate_name=record.get("resume", {}).get("name") or "there",
        reason=reason,
        role_scores=role_scores,
    )
    dry_run = bool(send_result.get("dry_run")) if isinstance(send_result, dict) else cfg.email_dry_run
    sent_at = datetime.now(timezone.utc)
    job_id = f"auto-rejection-{key}"
    subject = send_result.get("subject", "") if isinstance(send_result, dict) else ""
    message = send_result.get("message", reason) if isinstance(send_result, dict) else reason
    record["rejection_email"] = {
        "status": "dry_run" if dry_run else "sent",
        "job_id": job_id,
        "sent_at": sent_at,
        "subject": subject,
        "message": message,
    }
    history = record.get("email_history")
    if not isinstance(history, list):
        history = []
    record["email_history"] = sorted(
        [entry for entry in history if entry.get("job_id") != job_id]
        + [{
            "job_id": job_id,
            "action": "rejected",
            "role_id": "",
            "task_id": None,
            "sent_at": sent_at,
            "status": "sent",
            "dry_run": dry_run,
            "subject": subject,
        }],
        key=lambda entry: entry.get("sent_at") or datetime.min.replace(tzinfo=timezone.utc),
    )
    if not dry_run:
        record["status"] = "rejected"
    store.save(key, record)
    _persist_rejection_log(key, record, store)


def _persist_rejection_log(key: str, record: dict, store: Store) -> None:
    delivery = record.get("rejection_email", {})
    job_id = delivery.get("job_id")
    if not job_id:
        return
    status = delivery.get("status", "sent")
    sent_at = delivery.get("sent_at") or datetime.now(timezone.utc)
    email_log = {
        "_id": f"{job_id}-delivery",
        "job_id": job_id,
        "candidate_id": key,
        "candidate_name": (record.get("resume") or {}).get("name") or "Candidate",
        "candidate_email": (record.get("contact") or {}).get("emails", [None])[0],
        "recipient": (record.get("contact") or {}).get("emails", [None])[0],
        "action": "rejected",
        "role_id": "",
        "sent_at": sent_at,
        "status": status,
        "error": None,
        "dry_run": status == "dry_run",
        "subject": delivery.get("subject", ""),
        "message": delivery.get("message", ""),
    }
    job = {
        "_id": job_id,
        "action": "rejected",
        "role_id": "",
        "extra_ctx": {"automated": True},
        "candidate_ids": [key],
        "total": 1,
        "status": "done",
        "created_by": "resume_pipeline",
        "created_at": sent_at,
        "started_at": sent_at,
        "finished_at": sent_at,
        "results": {"sent": int(status == "sent"), "failed": 0, "skipped": int(status == "dry_run")},
        "automated": True,
    }
    store.log_rejection(job, email_log)


def process_message(
    raw: bytes,
    extract: Extractor,
    store: Store,
    files: ResumeFiles,
    matcher: RoleMatcher | None = None,
    email_config=None,
    email_sender=None,
) -> list[str]:
    """Returns the keys of every resume in the mail ([] if it has none)."""
    mail = parse_mail(raw)
    if not mail.attachments:
        log.info("no resume attachment: %r", mail.subject)
        return []

    keys = []
    for att in mail.attachments:
        key = make_key(mail.message_id or mail.date + mail.subject, att.filename)
        filename = key + Path(att.filename).suffix.lower()
        keys.append(key)

        if store.has(key):
            if not files.has(filename):  # record survived, file vanished: heal, no Gemini call
                files.write(filename, att.payload)
                log.warning("restored missing file %s", filename)
            else:
                log.info("already processed: %s", key)
            if email_config is not None:
                record = store.get(key)
                if record is not None:
                    _send_rejection_if_needed(
                        key, record, store, email_config, email_sender or send_rejection
                    )
            continue

        try:
            attachment_text = read_text(att)
        except Exception:
            if Path(att.filename).suffix.lower() != ".pdf":
                raise
            log.exception("text extraction failed for %s, retrying with OCR", att.filename)
            attachment_text = _ocr_pdf(att.payload)

        text, contacts = prepare(attachment_text)
        if (
            len(text) < MIN_TEXT_CHARS
            and len(attachment_text.strip()) >= MIN_TEXT_CHARS
            and Path(att.filename).suffix.lower() == ".pdf"
        ):
            log.info("PDF text unusable after cleanup for %s, retrying with OCR", att.filename)
            text, contacts = prepare(_ocr_pdf(att.payload))
        if len(text) < MIN_TEXT_CHARS:
            raise NoTextError(f"{att.filename}: only {len(text)} chars extracted")
        resume, meta = extract(text[:MAX_TEXT_CHARS])

        record = {
            "email": {
                "message_id": mail.message_id,
                "sender": mail.sender,
                "subject": mail.subject,
                "date": mail.date,
            },
            "body": mail.body,
            "contact": {"emails": contacts.emails, "phones": contacts.phones, "urls": contacts.urls},
            "resume_file": filename,
            "resume": resume,
        }
        matches = matcher(record) if matcher is not None else {}
        record["match"] = matches
        if matches:
            log.info("matched %s against %d role(s)", key, len(matches))
        else:
            log.warning("no role matches produced for %s", key)

        files.write(filename, att.payload)
        try:
            store.save(key, record)
        except Exception:
            files.remove(filename)  # no record -> no file
            raise
        if email_config is not None:
            _send_rejection_if_needed(key, record, store, email_config, email_sender or send_rejection)
        log.info("saved %s (%s in / %s out tokens)", key, meta.get("input_tokens"), meta.get("output_tokens"))
    return keys
