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
from pathlib import Path
from typing import Callable

from .config import MAX_TEXT_CHARS, MIN_TEXT_CHARS
from .files import ResumeFiles
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


def process_message(raw: bytes, extract: Extractor, store: Store, files: ResumeFiles) -> list[str]:
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

        files.write(filename, att.payload)
        try:
            store.save(key, record)
        except Exception:
            files.remove(filename)  # no record -> no file
            raise
        log.info("saved %s (%s in / %s out tokens)", key, meta.get("input_tokens"), meta.get("output_tokens"))
    return keys
