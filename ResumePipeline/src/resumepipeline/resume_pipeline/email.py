"""Render rejection messages and deliver them synchronously over SMTP."""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from mako.lookup import TemplateLookup

from .config import Config

log = logging.getLogger(__name__)
_templates = TemplateLookup(
    directories=[str(Path(__file__).parent / "templates")],
    input_encoding="utf-8",
    strict_undefined=True,
)


def send_rejection(
    cfg: Config,
    *,
    to_addr: str,
    candidate_name: str,
    reason: str,
    role_scores: list[dict[str, str]],
) -> dict[str, str | bool]:
    """Render the rejection template and send it, raising on delivery failure."""
    rendered = _templates.get_template("rejection.md.mako").render(
        candidate_name=candidate_name.strip() or "there",
        org_name=cfg.email_org_name,
        sender_name=cfg.email_sender_name,
        reason=reason,
        role_scores=role_scores,
    ).strip()
    lines = rendered.splitlines()
    subject_line = next((line for line in lines if line.startswith("Subject:")), None)
    if subject_line is None:
        raise ValueError("rejection template must include a Subject: line")
    subject_index = lines.index(subject_line)

    message = EmailMessage()
    message["Subject"] = subject_line.removeprefix("Subject:").strip()
    message["From"] = f"{cfg.email_sender_name} <{cfg.email_smtp_user}>"
    message["To"] = to_addr
    body = "\n".join(lines[subject_index + 1 :]).strip()
    message.set_content(body)

    if cfg.email_dry_run:
        log.info("dry run: rejection email to %s was not sent", to_addr)
        return {"subject": str(message["Subject"]), "message": body, "dry_run": True}
    if not cfg.email_smtp_user or not cfg.email_smtp_password:
        raise RuntimeError("EMAIL_SMTP_USER and EMAIL_SMTP_PASSWORD are required for email delivery")

    context = ssl.create_default_context()
    if cfg.email_smtp_tls:
        with smtplib.SMTP_SSL(cfg.email_smtp_host, cfg.email_smtp_port, context=context) as smtp:
            smtp.login(cfg.email_smtp_user, cfg.email_smtp_password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(cfg.email_smtp_host, cfg.email_smtp_port) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.login(cfg.email_smtp_user, cfg.email_smtp_password)
            smtp.send_message(message)
    return {"subject": str(message["Subject"]), "message": body, "dry_run": False}