from __future__ import annotations

import anyio.to_thread

from resumehub.app.core import db
from resumehub.app.core.plugin import AdminResource, AppContext, Module

from . import adapter
from .router import router


class MatchingModule(Module):
    name = "matching"
    description = "Runs the resume_matcher (single, per-role, all) and serves stored results."
    depends_on = ("resumes", "job_roles")
    permissions = {
        "matching:read": "View stored matches, leaderboards and job status",
        "matching:run": "Match one resume against one role",
        "matching:run_bulk": "Start bulk matching jobs (per role / everything)",
        "matching:manage": "Delete stored match results",
    }
    admin_resources = (
        AdminResource(
            key="match_jobs", label="Matching jobs", endpoint="/matching/jobs",
            columns=(("Id", "_id"), ("Kind", "kind"), ("Scope", "scope"), ("Status", "status"), ("By", "created_by")),
            read="matching:read",
            description="Start jobs with POST /matching/run-all or /matching/roles/{id}/run.",
        ),
    )

    def router(self):
        return router

    async def ensure_indexes(self, ctx: AppContext) -> None:
        await db.match_jobs().create_index("created_at", expireAfterSeconds=60 * 60 * 24 * 30)
        await db.match_jobs().create_index("status")

    async def on_startup(self, ctx: AppContext) -> None:
        # jobs that were running when the previous process died can never finish
        await db.match_jobs().update_many(
            {"status": {"$in": ["queued", "running"]}},
            {"$set": {"status": "failed", "error": "interrupted by restart"}},
        )

    async def stats(self, ctx: AppContext):
        return {
            "active_match_jobs": await db.match_jobs().count_documents({"status": {"$in": ["queued", "running"]}}),
            "matcher_available": await anyio.to_thread.run_sync(adapter.available),
        }


module = MatchingModule()
