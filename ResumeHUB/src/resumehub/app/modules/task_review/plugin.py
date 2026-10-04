from __future__ import annotations

from resumehub.app.core.plugin import AdminResource, AppContext, Module

from .router import _subs, _tasks, router


class TaskReviewModule(Module):
    name = "task_review"
    description = "Recruiters post hiring tasks per role; candidates submit demo video, project and repo URLs."
    depends_on = ("resumes", "job_roles")

    permissions = {
        "task_review:read":   "List and view hiring tasks",
        "task_review:create": "Create hiring tasks (recruiter)",
        "task_review:update": "Edit hiring tasks (recruiter)",
        "task_review:delete": "Delete hiring tasks and submissions (recruiter)",
        "task_review:submit": "Submit or update a task submission (candidate / recruiter on behalf)",
        "task_review:review": "Read submissions and write verdicts (recruiter)",
    }

    admin_resources = (
        AdminResource(
            key="hiring_tasks",
            label="Hiring tasks",
            endpoint="/task-review/tasks",
            columns=(
                ("Id", "_id"), ("Role", "role_id"), ("Title", "title"),
                ("Open", "is_open"), ("Deadline", "deadline"), ("By", "created_by"),
            ),
            read="task_review:read",
            create="task_review:create",
            update="task_review:update",
            delete="task_review:delete",
            readonly_fields=("_id", "created_at", "updated_at", "created_by"),
            create_template={
                "role_id": "junior-python-backend",
                "title": "Take-home task",
                "description": "Build a small REST API …",
                "instructions": "1. Fork the repo …",
                "deadline": None,
                "is_open": True,
            },
        ),
        AdminResource(
            key="task_submissions",
            label="Submissions",
            endpoint="/task-review/submissions",
            columns=(
                ("Id", "_id"), ("Task", "task_id"), ("Candidate", "candidate_name"),
                ("Status", "status"), ("Score", "review_score"), ("Submitted", "submitted_at"),
            ),
            read="task_review:review",
            update="task_review:review",   # PATCH /submissions/{id}/review is a separate action
            delete="task_review:delete",
            readonly_fields=("_id", "task_id", "role_id", "candidate_id", "submitted_at", "submitted_by"),
            description="To write a verdict use POST /task-review/submissions/{id}/review.",
        ),
    )

    def router(self):
        return router

    async def ensure_indexes(self, ctx: AppContext) -> None:
        await _tasks().create_index("role_id")
        await _tasks().create_index("is_open")
        await _tasks().create_index("created_at")
        await _subs().create_index([("task_id", 1), ("candidate_id", 1)], unique=True)
        await _subs().create_index("candidate_id")
        await _subs().create_index("status")
        await _subs().create_index("submitted_at")

    async def stats(self, ctx: AppContext) -> dict:
        return {
            "hiring_tasks": await _tasks().count_documents({}),
            "open_hiring_tasks": await _tasks().count_documents({"is_open": True}),
            "task_submissions": await _subs().count_documents({}),
            "submissions_pending": await _subs().count_documents({"status": "pending"}),
            "submissions_accepted": await _subs().count_documents({"status": "accepted"}),
        }


module = TaskReviewModule()
