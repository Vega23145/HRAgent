from __future__ import annotations

import logging

from resumehub.app.core import db
from resumehub.app.core.plugin import AdminResource, AppContext, Module

from .router import router

log = logging.getLogger("hub.resumes")


class ResumesModule(Module):
    name = "resumes"
    description = "CRUD, search and file download for parsed resumes. The matcher owns the 'match' block."
    permissions = {
        "resumes:read": "List and view resumes (contact details redacted)",
        "resumes:read_pii": "See and write contact details, mail body and sender",
        "resumes:create": "Create resumes",
        "resumes:update": "Edit resumes",
        "resumes:delete": "Delete resumes",
        "resumes:download": "Download the original resume file",
    }
    admin_resources = (
        AdminResource(
            key="resumes", label="Resumes", endpoint="/resumes",
            columns=(("Id", "_id"), ("Name", "name"), ("Subject", "subject"), ("Scores", "scores")),
            read="resumes:read", create="resumes:create", update="resumes:update", delete="resumes:delete",
            readonly_fields=("_id", "match", "_redacted"),
            create_template={"resume": {"name": "", "skills": [], "experience": [], "education": [], "projects": []}},
            description="'match' is written by the matcher and is read-only here.",
        ),
    )

    def router(self):
        return router

    async def ensure_indexes(self, ctx: AppContext) -> None:
        col = db.resumes()
        await col.create_index("resume.name")
        await col.create_index("resume.skills.items")
        try:
            await col.create_index(
                "email.message_id", unique=True,
                partialFilterExpression={"email.message_id": {"$type": "string"}},
            )
        except Exception:  # noqa: BLE001 - existing duplicates must not stop the API
            log.warning("could not create unique index on email.message_id (duplicates already stored?)")

    async def stats(self, ctx: AppContext):
        col = db.resumes()
        return {
            "resumes": await col.count_documents({}),
            "resumes_with_matches": await col.count_documents({"match": {"$exists": True, "$ne": {}}}),
        }


module = ResumesModule()
