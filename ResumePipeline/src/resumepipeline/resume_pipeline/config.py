import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # ignore anything bigger
MAX_TEXT_CHARS = 30_000  # hard cap on what is ever sent to the model
MIN_TEXT_CHARS = 50  # below this the PDF is probably a scan (no text layer)
ORPHAN_GRACE_S = 600  # a file with no record is only swept after this long
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


@dataclass(frozen=True)
class Config:
    imap_host: str
    imap_user: str
    imap_password: str
    imap_folder: str
    gemini_api_key: str
    gemini_model: str
    gemini_thinking_level: str
    resume_dir: str
    mongo_uri: str
    mongo_db: str
    mongo_collection: str
    out_dir: str
    role_db: str = "resume_hub"
    role_collection: str = "roles"
    auto_reject_score_threshold: float | None = None
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 465
    email_smtp_tls: bool = True
    email_smtp_user: str = ""
    email_smtp_password: str = ""
    email_sender_name: str = "Hiring Team"
    email_org_name: str = "Our Company"
    email_dry_run: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv(_ENV_FILE, override=False)
        e = os.environ.get
        mongo_uri = e("HUB_MONGO_URI", e("MONGO_URI", ""))
        mongo_db = e("HUB_MONGO_DB", e("MONGO_DB", "resume_hub"))
        threshold_value = e("EMAIL_AUTO_REJECT_SCORE_THRESHOLD", "").strip()
        threshold = float(threshold_value) if threshold_value else None
        if threshold is not None and not 0 <= threshold <= 100:
            raise ValueError("EMAIL_AUTO_REJECT_SCORE_THRESHOLD must be between 0 and 100")
        tls_value = e("EMAIL_SMTP_TLS", "true").lower()
        if tls_value not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError("EMAIL_SMTP_TLS must be a boolean")
        dry_run_value = e("EMAIL_DRY_RUN", "false").lower()
        if dry_run_value not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError("EMAIL_DRY_RUN must be a boolean")
        return cls(
            imap_host=e("IMAP_HOST", ""),
            imap_user=e("IMAP_USER", ""),
            imap_password=e("IMAP_PASSWORD", ""),
            imap_folder=e("IMAP_FOLDER", "INBOX"),
            gemini_api_key=e("GEMINI_API_KEY", ""),
            gemini_model=e("GEMINI_MODEL", "gemini-2.5-flash-lite"),
            gemini_thinking_level=e("GEMINI_THINKING_LEVEL", ""),
            resume_dir=e("RESUME_DIR", "resumes"),
            mongo_uri=mongo_uri,
            mongo_db=mongo_db,
            mongo_collection=e("HUB_RESUME_COLLECTION", e("MONGO_COLLECTION", "resumes")),
            out_dir=e("OUT_DIR", "out"),
            role_db=e("HUB_ROLE_MONGO_DB", mongo_db),
            role_collection=e("HUB_ROLE_COLLECTION", "roles"),
            auto_reject_score_threshold=threshold,
            email_smtp_host=e("EMAIL_SMTP_HOST", "smtp.gmail.com"),
            email_smtp_port=int(e("EMAIL_SMTP_PORT", "465")),
            email_smtp_tls=tls_value in {"true", "1", "yes"},
            email_smtp_user=e("EMAIL_SMTP_USER", ""),
            email_smtp_password=e("EMAIL_SMTP_PASSWORD", ""),
            email_sender_name=e("EMAIL_SENDER_NAME", "Hiring Team"),
            email_org_name=e("EMAIL_ORG_NAME", "Our Company"),
            email_dry_run=dry_run_value in {"true", "1", "yes"},
        )
