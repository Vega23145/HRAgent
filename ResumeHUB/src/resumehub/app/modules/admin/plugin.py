from __future__ import annotations

from pathlib import Path

from fastapi.staticfiles import StaticFiles

from resumehub.app.core import db
from resumehub.app.core.plugin import AdminResource, AppContext, Module

from .router import router

STATIC = Path(__file__).parent / "static"


class AdminModule(Module):
    name = "admin"
    description = "Admin panel (manifest-driven UI at /admin), dashboard stats and audit log."
    permissions = {
        "admin:access": "Open the admin panel",
        "admin:audit": "Read the audit log",
    }
    admin_resources = (
        AdminResource(
            key="audit", label="Audit log", endpoint="/admin/audit",
            columns=(("Time", "ts"), ("Actor", "actor_email"), ("Action", "action"), ("Resource", "resource"), ("Id", "resource_id")),
            read="admin:audit", readonly_fields=("_id",),
        ),
    )

    def router(self):
        return router

    def mounts(self):
        return [("/admin", StaticFiles(directory=STATIC, html=True), "admin-ui")]

    async def ensure_indexes(self, ctx: AppContext) -> None:
        await db.audit_log().create_index("ts", expireAfterSeconds=60 * 60 * 24 * 365)
        await db.audit_log().create_index("actor_email")


module = AdminModule()
