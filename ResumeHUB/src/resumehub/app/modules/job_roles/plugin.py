from __future__ import annotations

from resumehub.app.core import db
from resumehub.app.core.plugin import AdminResource, AppContext, Module

from .router import router

_TEMPLATE = {
    "_id": "junior-example-role",
    "title": "Junior Example Role",
    "description": "",
    "department": "Engineering",
    "team": "",
    "employment_type": "full-time",
    "work_mode": "hybrid",
    "experience_level": "junior",
    "responsibilities": [],
    "tech_stack": [],
    "nice_to_have": [],
    "required_skills": [{"name": "python", "weight": 2.0}],
    "min_years": 0.5,
    "seniority": 1,
    "w_skills": 0.40,
    "w_years": 0.25,
    "w_seniority": 0.20,
    "w_relevance": 0.15,
}


class JobRolesModule(Module):
    name = "job_roles"
    description = "CRUD for the job roles collection that resumes are matched against."
    permissions = {
        "job_roles:read": "List and view job roles",
        "job_roles:create": "Create job roles",
        "job_roles:update": "Edit job roles",
        "job_roles:delete": "Delete job roles",
    }
    admin_resources = (
        AdminResource(
            key="job_roles", label="Job roles", endpoint="/job-roles",
            columns=(("Id", "_id"), ("Title", "title"), ("Dept", "department"), ("Level", "experience_level"), ("Mode", "work_mode")),
            read="job_roles:read", create="job_roles:create", update="job_roles:update",
            delete="job_roles:delete", update_method="PUT", create_template=_TEMPLATE,
            description="Re-run matching after changing weights or skills; stored scores are not recomputed automatically.",
        ),
    )

    def router(self):
        return router

    async def ensure_indexes(self, ctx: AppContext) -> None:
        await db.job_roles().create_index("department")
        await db.job_roles().create_index("required_skills.name")

    async def stats(self, ctx: AppContext):
        return {"job_roles": await db.job_roles().count_documents({})}


module = JobRolesModule()
