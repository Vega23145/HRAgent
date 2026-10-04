import os
from dataclasses import dataclass

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # ignore anything bigger
MAX_TEXT_CHARS = 30_000  # hard cap on what is ever sent to the model
MIN_TEXT_CHARS = 50  # below this the PDF is probably a scan (no text layer)
ORPHAN_GRACE_S = 600  # a file with no record is only swept after this long


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

    @classmethod
    def from_env(cls) -> "Config":
        e = os.environ.get
        return cls(
            imap_host=e("IMAP_HOST", ""),
            imap_user=e("IMAP_USER", ""),
            imap_password=e("IMAP_PASSWORD", ""),
            imap_folder=e("IMAP_FOLDER", "INBOX"),
            gemini_api_key=e("GEMINI_API_KEY", ""),
            gemini_model=e("GEMINI_MODEL", "gemini-2.5-flash-lite"),
            gemini_thinking_level=e("GEMINI_THINKING_LEVEL", ""),
            resume_dir=e("RESUME_DIR", "resumes"),
            mongo_uri=e("HUB_MONGO_URI", e("MONGO_URI", "")),
            mongo_db=e("HUB_MONGO_DB", e("MONGO_DB", "resumes")),
            mongo_collection=e("HUB_RESUME_COLLECTION", e("MONGO_COLLECTION", "resumes")),
            out_dir=e("OUT_DIR", "out"),
        )
