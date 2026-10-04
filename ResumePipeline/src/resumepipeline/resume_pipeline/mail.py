"""Mail side: IMAP access + MIME parsing. Stdlib only."""
from __future__ import annotations

import email
import imaplib
import re
from dataclasses import dataclass, field
from email import policy
from pathlib import Path
from typing import Iterator

from .config import MAX_ATTACHMENT_BYTES

ALLOWED_EXT = {".pdf", ".docx", ".tex", ".latex"}


@dataclass
class Attachment:
    filename: str
    payload: bytes


@dataclass
class ParsedMail:
    message_id: str
    sender: str
    subject: str
    date: str
    body: str
    attachments: list[Attachment] = field(default_factory=list)


def parse_mail(raw: bytes) -> ParsedMail:
    msg = email.message_from_bytes(raw, policy=policy.default)

    part = msg.get_body(preferencelist=("plain", "html"))
    body = part.get_content() if part else ""
    if part is not None and part.get_content_type() == "text/html":
        body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))

    attachments = []
    for p in msg.iter_attachments():
        name = p.get_filename() or ""
        data = p.get_payload(decode=True) or b""
        if Path(name).suffix.lower() in ALLOWED_EXT and 0 < len(data) <= MAX_ATTACHMENT_BYTES:
            attachments.append(Attachment(name, data))

    return ParsedMail(
        message_id=str(msg["Message-ID"] or "").strip(),
        sender=str(msg["From"] or ""),
        subject=str(msg["Subject"] or ""),
        date=str(msg["Date"] or ""),
        body=body.strip(),
        attachments=attachments,
    )


class Mailbox:
    """One IMAP session. Messages are only marked \\Seen when you say so,
    i.e. after the JSON is safely on disk, so a crash means retry, not loss."""

    def __init__(self, host: str, user: str, password: str, folder: str = "INBOX"):
        self._args = (host, user, password, folder)
        self._imap: imaplib.IMAP4_SSL | None = None

    def __enter__(self) -> "Mailbox":
        host, user, password, folder = self._args
        self._imap = imaplib.IMAP4_SSL(host)
        self._imap.login(user, password)
        self._imap.select(folder)
        return self

    def __exit__(self, *exc) -> None:
        try:
            self._imap.close()
            self._imap.logout()
        except imaplib.IMAP4.error:
            pass

    def unseen(self) -> Iterator[tuple[bytes, bytes]]:
        _, data = self._imap.uid("search", None, "UNSEEN")
        for uid in data[0].split():
            _, msg = self._imap.uid("fetch", uid, "(BODY.PEEK[])")  # PEEK: don't mark read
            if msg and msg[0]:
                yield uid, msg[0][1]

    def mark_seen(self, uid: bytes) -> None:
        self._imap.uid("store", uid, "+FLAGS", "\\Seen")