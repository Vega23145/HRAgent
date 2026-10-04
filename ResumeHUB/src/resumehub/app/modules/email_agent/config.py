from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmailSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EMAIL_", extra="ignore")

    # SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_tls: bool = True          # True = SMTP_SSL; False = STARTTLS
    smtp_user: str = ""
    smtp_password: str = ""

    # Branding (injected into every template)
    sender_name: str = "Hiring Team"
    org_name: str = "Our Company"

    # Safety
    dry_run: bool = False          # True = skip actual send, log instead
    max_bulk: int = Field(500, ge=1, le=5000)   # hard cap per bulk job


@lru_cache
def get_email_settings() -> EmailSettings:
    return EmailSettings()
