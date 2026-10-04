from __future__ import annotations

import re
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, Response

from resumehub.app.core import db
from resumehub.app.core.audit import audit
from resumehub.app.core.deps import Page, Principal, paged, pagination, require
from resumehub.app.core.utils import SLUG_PATTERN, utcnow

from .schemas import SubmissionCreate, SubmissionReview, TaskCreate, TaskUpdate

router = APIRouter()
TaskId   = Annotated[str, Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{3,63}$")]
SubId    = Annotated[str, Path(description="Submission _id (hex uuid)")]
RoleId   = Annotated[str, Path(pattern=SLUG_PATTERN)]

# ── helpers ──────────────────────────────────────────────────────────────────

def _rx(q: str) -> dict:
    return {"$regex": re.escape(q), "$options": "i"}


def _tasks():  return db.get_db()["hiring_tasks"]
def _subs():   return db.get_db()["task_submissions"]


async def _get_task_or_404(task_id: str) -> dict:
    doc = await _tasks().find_one({"_id": task_id})
    if not doc:
        raise HTTPException(404, "Hiring task not found")
    return doc


async def _get_sub_or_404(sub_id: str) -> dict:
    doc = await _subs().find_one({"_id": sub_id})
    if not doc:
        raise HTTPException(404, "Submission not found")
    return doc


# ═══════════════════════════════════════════════════════════════════════════
# HIRING TASKS  (recruiter-owned)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/tasks")
async def list_tasks(
    q: str | None = None,
    role_id: str | None = None,
    is_open: bool | None = None,
    p: Page = Depends(pagination),
    _: Principal = Depends(require("task_review:read")),
):
    filt: dict = {}
    if q:
        filt["$or"] = [{"title": _rx(q)}, {"description": _rx(q)}]
    if role_id:
        filt["role_id"] = role_id
    if is_open is not None:
        filt["is_open"] = is_open
    total = await _tasks().count_documents(filt)
    cur = _tasks().find(filt).sort("created_at", -1).skip(p.skip).limit(p.size)
    return paged(await cur.to_list(), total, p)


@router.post("/tasks", status_code=201)
async def create_task(body: TaskCreate, request: Request, actor: Principal = Depends(require("task_review:create"))):
    # verify the role exists
    if not await db.job_roles().find_one({"_id": body.role_id}, {"_id": 1}):
        raise HTTPException(422, f"Job role '{body.role_id}' not found")
    now = utcnow()
    doc = {
        "_id": uuid.uuid4().hex[:16],
        "role_id": body.role_id,
        "title": body.title,
        "description": body.description,
        "instructions": body.instructions,
        "deadline": body.deadline,
        "is_open": body.is_open,
        "created_by": actor.email,
        "created_at": now,
        "updated_at": now,
    }
    await _tasks().insert_one(doc)
    await audit(actor, "task_review.task.create", "hiring_tasks", doc["_id"],
                {"role_id": body.role_id, "title": body.title}, request)
    return doc


@router.get("/tasks/{task_id}")
async def get_task(task_id: TaskId, _: Principal = Depends(require("task_review:read"))):
    return await _get_task_or_404(task_id)


@router.patch("/tasks/{task_id}")
async def update_task(task_id: TaskId, body: TaskUpdate, request: Request,
                      actor: Principal = Depends(require("task_review:update"))):
    doc = await _get_task_or_404(task_id)
    sets = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not sets:
        raise HTTPException(400, "Nothing to update")
    sets["updated_at"] = utcnow()
    await _tasks().update_one({"_id": task_id}, {"$set": sets})
    await audit(actor, "task_review.task.update", "hiring_tasks", task_id,
                {"fields": sorted(k for k in sets if k != "updated_at")}, request)
    return await _tasks().find_one({"_id": task_id})


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: TaskId, request: Request,
                      actor: Principal = Depends(require("task_review:delete"))):
    await _get_task_or_404(task_id)
    in_use = await _subs().count_documents({"task_id": task_id})
    if in_use:
        raise HTTPException(409, f"Task has {in_use} submission(s); delete them first or close the task")
    await _tasks().delete_one({"_id": task_id})
    await audit(actor, "task_review.task.delete", "hiring_tasks", task_id, request=request)
    return Response(status_code=204)


# ═══════════════════════════════════════════════════════════════════════════
# SUBMISSIONS  (candidate-facing write; recruiter-facing read + review)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/tasks/{task_id}/submissions")
async def list_submissions(
    task_id: TaskId,
    status: Literal["pending", "under_review", "accepted", "rejected"] | None = None,
    q: str | None = None,
    p: Page = Depends(pagination),
    _: Principal = Depends(require("task_review:review")),
):
    await _get_task_or_404(task_id)
    filt: dict = {"task_id": task_id}
    if status:
        filt["status"] = status
    if q:
        filt["$or"] = [{"candidate_name": _rx(q)}, {"candidate_email": _rx(q)},
                       {"candidate_id": _rx(q)}]
    total = await _subs().count_documents(filt)
    cur = _subs().find(filt).sort("submitted_at", -1).skip(p.skip).limit(p.size)
    return paged(await cur.to_list(), total, p)


@router.post("/tasks/{task_id}/submissions", status_code=201)
async def submit_task(task_id: TaskId, body: SubmissionCreate, request: Request,
                      actor: Principal = Depends(require("task_review:submit"))):
    """
    The candidate (or a recruiter on their behalf) submits deliverables.
    One candidate may have at most one submission per task.
    """
    task = await _get_task_or_404(task_id)
    if not task.get("is_open", True):
        raise HTTPException(409, "This task is no longer accepting submissions")

    dup = await _subs().find_one({"task_id": task_id, "candidate_id": body.candidate_id})
    if dup:
        raise HTTPException(409,
            f"Candidate '{body.candidate_id}' already has a submission for this task (id={dup['_id']}). "
            "PATCH it instead.")

    # soft link to the resume collection (no hard FK in Mongo)
    if not await db.resumes().find_one({"_id": body.candidate_id}, {"_id": 1}):
        raise HTTPException(422, f"Resume '{body.candidate_id}' not found in resumes collection")

    now = utcnow()
    doc = {
        "_id": uuid.uuid4().hex,
        "task_id": task_id,
        "role_id": task["role_id"],
        # candidate identity
        "candidate_id": body.candidate_id,
        "candidate_name": body.candidate_name,
        "candidate_email": body.candidate_email,
        # deliverables
        "demo_video_url": str(body.demo_video_url),
        "project_url": str(body.project_url) if body.project_url else None,
        "repo_url": str(body.repo_url) if body.repo_url else None,
        "notes": body.notes,
        # review state (set by recruiter later)
        "status": "pending",
        "review_notes": "",
        "review_score": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "submitted_at": now,
        "updated_at": now,
        "submitted_by": actor.email,
    }
    await _subs().insert_one(doc)
    await audit(actor, "task_review.submit", "task_submissions", doc["_id"],
                {"task_id": task_id, "candidate_id": body.candidate_id}, request)
    return doc


@router.get("/submissions/{sub_id}")
async def get_submission(sub_id: SubId, actor: Principal = Depends(require("task_review:review"))):
    return await _get_sub_or_404(sub_id)


@router.patch("/submissions/{sub_id}")
async def update_submission(sub_id: SubId, body: SubmissionCreate, request: Request,
                            actor: Principal = Depends(require("task_review:submit"))):
    """Candidate can update their own submission while the task is still open."""
    sub = await _get_sub_or_404(sub_id)
    task = await _get_task_or_404(sub["task_id"])
    if not task.get("is_open", True):
        raise HTTPException(409, "Task is closed; submission can no longer be updated")
    if sub.get("status") not in ("pending", None):
        raise HTTPException(409, "Submission is already under review or decided; it can no longer be changed")

    sets = body.model_dump(exclude_unset=True)
    sets["updated_at"] = utcnow()
    # deliverables only – identity and candidate_id may not change
    sets.pop("candidate_id", None)
    for url_field in ("demo_video_url", "project_url", "repo_url"):
        if url_field in sets and sets[url_field] is not None:
            sets[url_field] = str(sets[url_field])
    await _subs().update_one({"_id": sub_id}, {"$set": sets})
    await audit(actor, "task_review.submission.update", "task_submissions", sub_id, request=request)
    return await _subs().find_one({"_id": sub_id})


@router.post("/submissions/{sub_id}/review")
async def review_submission(sub_id: SubId, body: SubmissionReview, request: Request,
                            actor: Principal = Depends(require("task_review:review"))):
    """Recruiter writes a verdict."""
    await _get_sub_or_404(sub_id)
    now = utcnow()
    sets = {
        "status": body.status,
        "review_notes": body.notes,
        "review_score": body.score,
        "reviewed_by": actor.email,
        "reviewed_at": now,
        "updated_at": now,
    }
    await _subs().update_one({"_id": sub_id}, {"$set": sets})
    await audit(actor, "task_review.review", "task_submissions", sub_id,
                {"status": body.status, "score": body.score}, request)
    return await _subs().find_one({"_id": sub_id})


@router.delete("/submissions/{sub_id}", status_code=204)
async def delete_submission(sub_id: SubId, request: Request,
                            actor: Principal = Depends(require("task_review:delete"))):
    if not await _subs().find_one({"_id": sub_id}, {"_id": 1}):
        raise HTTPException(404, "Submission not found")
    await _subs().delete_one({"_id": sub_id})
    await audit(actor, "task_review.submission.delete", "task_submissions", sub_id, request=request)
    return Response(status_code=204)


# ── cross-cutting read: all submissions for a candidate ───────────────────

@router.get("/candidates/{candidate_id}/submissions")
async def candidate_submissions(
    candidate_id: str,
    p: Page = Depends(pagination),
    _: Principal = Depends(require("task_review:review")),
):
    filt = {"candidate_id": candidate_id}
    total = await _subs().count_documents(filt)
    cur = _subs().find(filt).sort("submitted_at", -1).skip(p.skip).limit(p.size)
    return paged(await cur.to_list(), total, p)
