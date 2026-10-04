"""SMTP sender.  Reads credentials from settings; runs synchronously inside a thread pool."""
from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import EmailSettings


def send(cfg: EmailSettings, *, to_addr: str, subject: str, body: str) -> None:
    """Send one plain-text / HTML email. Raises on any SMTP error."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{cfg.sender_name} <{cfg.smtp_user}>"
    msg["To"] = to_addr

    # plain text
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # minimal HTML: wrap in <pre> so Markdown-ish text looks decent
    html = f"<html><body><pre style='font-family:sans-serif;white-space:pre-wrap'>{_esc(body)}</pre></body></html>"
    msg.attach(MIMEText(html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    if cfg.smtp_tls:
        with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=ctx) as s:
            s.login(cfg.smtp_user, cfg.smtp_password)
            s.sendmail(cfg.smtp_user, [to_addr], msg.as_bytes())
    else:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.login(cfg.smtp_user, cfg.smtp_password)
            s.sendmail(cfg.smtp_user, [to_addr], msg.as_bytes())


def _esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
