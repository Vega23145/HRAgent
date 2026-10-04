from __future__ import annotations

import logging
import uuid

from resumehub.app.core import db
from resumehub.app.core.config import DEFAULT_ADMIN_PASSWORD
from resumehub.app.core.plugin import AppContext
from resumehub.app.core.security import hash_password
from resumehub.app.core.utils import utcnow

log = logging.getLogger("hub.users")

BUILTIN_ROLES = {
    "admin": ("Full access to everything", ["*"]),
    "recruiter": (
        "Works resumes and runs matching",
        [
            "resumes:read", "resumes:read_pii", "resumes:create", "resumes:update",
            "resumes:download", "job_roles:read", "matching:read", "matching:run",
        ],
    ),
    "viewer": ("Read-only, no personal data", ["resumes:read", "job_roles:read", "matching:read"]),
}


async def ensure_defaults(ctx: AppContext) -> None:
    now = utcnow()
    for name, (desc, perms) in BUILTIN_ROLES.items():
        await db.access_roles().update_one(
            {"_id": name},
            {
                "$setOnInsert": {
                    "description": desc,
                    "permissions": perms,
                    "builtin": True,
                    "created_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
    # the admin role is always "*", even if someone tampered with the stored document
    await db.access_roles().update_one({"_id": "admin"}, {"$set": {"permissions": ["*"], "builtin": True}})

    if await db.users().count_documents({}) == 0:
        s = ctx.settings
        if s.bootstrap_admin_password == DEFAULT_ADMIN_PASSWORD:
            log.warning("bootstrapping admin with the DEFAULT password - change it immediately")
        await db.users().insert_one(
            {
                "_id": uuid.uuid4().hex,
                "email": s.bootstrap_admin_email.strip().lower(),
                "full_name": "Administrator",
                "password_hash": hash_password(s.bootstrap_admin_password),
                "is_active": True,
                "roles": ["admin"],
                "grants": [],
                "denies": [],
                "token_version": 0,
                "created_at": now,
                "updated_at": now,
            }
        )
        log.info("created bootstrap admin %s", s.bootstrap_admin_email)
