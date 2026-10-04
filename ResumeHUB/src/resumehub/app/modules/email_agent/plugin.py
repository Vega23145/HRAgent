from __future__ import annotations

from resumehub.app.core import db
from resumehub.app.core.plugin import AdminResource, AppContext, Module

from .router import router
from .worker import _emails, _jobs


class EmailAgentModule(Module):
    name        = "email_agent"
    description = "Send templated emails to candidates (single or bulk) and track delivery in background jobs."
    depends_on  = ("resumes",)          # soft dependency: job_roles / task_review used if present

    permissions = {
        "email_agent:read":   "View email jobs, logs and template previews",
        "email_agent:send":   "Send an email to a single candidate",
        "email_agent:bulk":   "Start a bulk email job (recruiter)",
        "email_agent:manage": "Delete completed email jobs",
    }

    admin_resources = (
        AdminResource(
            key="email_jobs",
            label="Email jobs",
            endpoint="/email-agent/jobs",
            columns=(
                ("Id", "_id"), ("Action", "action"), ("Role", "role_id"),
                ("Total", "total"), ("Status", "status"), ("By", "created_by"), ("Created", "created_at"),
            ),
            read="email_agent:read",
            delete="email_agent:manage",
            readonly_fields=("_id", "candidate_ids", "extra_ctx", "created_at", "started_at", "finished_at", "results"),
            description="Start jobs via POST /email-agent/send or /email-agent/bulk.",
        ),
    )

    def router(self):
        return router

    async def ensure_indexes(self, ctx: AppContext) -> None:
        await _jobs().create_index("created_at")
        await _jobs().create_index("status")
        await _jobs().create_index("action")
        await _emails().create_index("job_id")
        await _emails().create_index("candidate_id")
        await _emails().create_index("sent_at", expireAfterSeconds=60 * 60 * 24 * 180)  # 6 months

    async def on_startup(self, ctx: AppContext) -> None:
        # jobs that were running when the process died
        await _jobs().update_many(
            {"status": {"$in": ["queued", "running"]}},
            {"$set": {"status": "failed", "results": {"error": "interrupted by restart"}}},
        )

    async def stats(self, ctx: AppContext) -> dict:
        return {
            "email_jobs_total":   await _jobs().count_documents({}),
            "email_jobs_running": await _jobs().count_documents({"status": {"$in": ["queued", "running"]}}),
            "emails_sent":        await _emails().count_documents({"status": "sent"}),
            "emails_failed":      await _emails().count_documents({"status": "failed"}),
        }


module = EmailAgentModule()
