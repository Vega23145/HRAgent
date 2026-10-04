from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from resumehub.app.core import db
from resumehub.app.core.audit import audit
from resumehub.app.core.deps import Page, Principal, paged, pagination, require
from resumehub.app.core.utils import SLUG_PATTERN, utcnow

from .renderer import ACTION_TEMPLATES, list_templates
from .worker import _emails, _jobs, execute_job

router = APIRouter()
RoleId = Annotated[str, Field(pattern=SLUG_PATTERN)]

# ── Mongo helpers ──────────────────────────────────────────────────────────

async def _create_job(
    actor: Principal,
    action: str,
    candidate_ids: list[str],
    role_id: str,
    extra_ctx: dict,
) -> dict:
    if not candidate_ids:
        raise HTTPException(422, "No candidates matched the filter")
    cfg_import = __import__("email_agent.config", fromlist=["get_email_settings"])
    cfg = cfg_import.get_email_settings()
    if len(candidate_ids) > cfg.max_bulk:
        raise HTTPException(422, f"Batch exceeds max_bulk={cfg.max_bulk}; narrow your filter")

    job: dict[str, Any] = {
        "_id":           uuid.uuid4().hex,
        "action":        action,
        "role_id":       role_id,
        "extra_ctx":     extra_ctx,
        "candidate_ids": candidate_ids,
        "total":         len(candidate_ids),
        "status":        "queued",
        "created_by":    actor.email,
        "created_at":    utcnow(),
        "started_at":    None,
        "finished_at":   None,
        "results":       None,
    }
    await _jobs().insert_one(job)
    return job


# ── Schemas ────────────────────────────────────────────────────────────────

class SingleSend(BaseModel):
    action: Literal["interview", "task_assigned", "rejected", "hired", "custom"]
    candidate_id: str
    role_id: str = ""
    # task_assigned extras
    task_id: str | None = None
    # custom extras
    subject: str | None = None
    body: str | None = None


class BulkFilter(BaseModel):
    action: Literal["interview", "task_assigned", "rejected", "hired", "custom"]
    role_id: str = Field("", description="Filter: candidates who applied / matched this role")
    # score filter (requires role_id)
    max_score: float | None = Field(None, ge=0, le=100, description="Include candidates with match score ≤ this")
    min_score: float | None = Field(None, ge=0, le=100, description="Include candidates with match score ≥ this")
    # or an explicit list of resume _ids (overrides score filter)
    candidate_ids: list[str] | None = None
    # task extras (for task_assigned)
    task_id: str | None = None
    # custom extras
    subject: str | None = None
    body: str | None = None


# ── Single send ────────────────────────────────────────────────────────────

@router.post("/send", status_code=202)
async def send_single(
    body: SingleSend,
    bg: BackgroundTasks,
    request: Request,
    actor: Principal = Depends(require("email_agent:send")),
):
    extra_ctx = await _build_extra_ctx(body.action, body.task_id, body.subject, body.body)
    candidate = await db.resumes().find_one({"_id": body.candidate_id})
    if not candidate:
        raise HTTPException(404, f"Resume '{body.candidate_id}' not found")

    job = await _create_job(actor, body.action, [body.candidate_id], body.role_id, extra_ctx)
    bg.add_task(execute_job, job["_id"])
    await audit(actor, "email_agent.send_single", "email_jobs", job["_id"],
                {"action": body.action, "to": body.candidate_id}, request)
    return job


# ── Bulk send ──────────────────────────────────────────────────────────────

@router.post("/bulk", status_code=202)
async def send_bulk(
    body: BulkFilter,
    bg: BackgroundTasks,
    request: Request,
    actor: Principal = Depends(require("email_agent:bulk")),
):
    candidate_ids: list[str]

    if body.candidate_ids:
        candidate_ids = body.candidate_ids
    else:
        candidate_ids = await _resolve_by_score(body.role_id, body.min_score, body.max_score)

    extra_ctx = await _build_extra_ctx(body.action, body.task_id, body.subject, body.body)
    job = await _create_job(actor, body.action, candidate_ids, body.role_id, extra_ctx)
    bg.add_task(execute_job, job["_id"])
    await audit(actor, "email_agent.bulk", "email_jobs", job["_id"],
                {"action": body.action, "count": len(candidate_ids), "role_id": body.role_id}, request)
    return job


async def _resolve_by_score(role_id: str, min_score, max_score) -> list[str]:
    if not role_id:
        raise HTTPException(422, "role_id is required when no explicit candidate_ids given")

    score_filt: dict[str, Any] = {}
    if min_score is not None:
        score_filt["$gte"] = min_score
    if max_score is not None:
        score_filt["$lte"] = max_score
    if not score_filt:
        raise HTTPException(422, "Provide min_score and/or max_score, or explicit candidate_ids")

    filt = {f"match.{role_id}.score": score_filt}
    docs = await db.resumes().find(filt, {"_id": 1}).to_list()
    return [d["_id"] for d in docs]


async def _build_extra_ctx(action: str, task_id, subject, body_text) -> dict:
    ctx: dict[str, Any] = {}
    if action == "task_assigned":
        if not task_id:
            raise HTTPException(422, "task_id is required for action=task_assigned")
        task = await db.get_db()["hiring_tasks"].find_one({"_id": task_id})
        if not task:
            raise HTTPException(404, f"Hiring task '{task_id}' not found")
        ctx["task_title"]        = task.get("title", "")
        ctx["task_description"]  = task.get("description", "")
        ctx["task_instructions"] = task.get("instructions", "")
        ctx["task_deadline"]     = task.get("deadline") or ""
    if action == "custom":
        if not subject or not body_text:
            raise HTTPException(422, "subject and body are required for action=custom")
        ctx["subject"] = subject
        ctx["body"]    = body_text
    return ctx


# ── Job status / log ───────────────────────────────────────────────────────

@router.get("/jobs")
async def list_jobs(
    status: str | None = None,
    action: str | None = None,
    p: Page = Depends(pagination),
    _: Principal = Depends(require("email_agent:read")),
):
    filt: dict = {}
    if status:
        filt["status"] = status
    if action:
        filt["action"] = action
    total = await _jobs().count_documents(filt)
    cur   = _jobs().find(filt).sort("created_at", -1).skip(p.skip).limit(p.size)
    return paged(await cur.to_list(), total, p)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, _: Principal = Depends(require("email_agent:read"))):
    doc = await _jobs().find_one({"_id": job_id})
    if not doc:
        raise HTTPException(404, "Job not found")
    return doc


@router.get("/jobs/{job_id}/log")
async def job_log(
    job_id: str,
    status: str | None = None,
    p: Page = Depends(pagination),
    _: Principal = Depends(require("email_agent:read")),
):
    filt: dict = {"job_id": job_id}
    if status:
        filt["status"] = status
    total = await _emails().count_documents(filt)
    cur   = _emails().find(filt).sort("sent_at", -1).skip(p.skip).limit(p.size)
    return paged(await cur.to_list(), total, p)


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str, request: Request, actor: Principal = Depends(require("email_agent:manage"))):
    doc = await _jobs().find_one({"_id": job_id})
    if not doc:
        raise HTTPException(404, "Job not found")
    if doc.get("status") in ("queued", "running"):
        raise HTTPException(409, "Cannot delete a running job")
    await _jobs().delete_one({"_id": job_id})
    await _emails().delete_many({"job_id": job_id})
    await audit(actor, "email_agent.job.delete", "email_jobs", job_id, request=request)
    return Response(status_code=204)


# ── Template introspection ─────────────────────────────────────────────────

@router.get("/templates")
async def list_tmpl(_: Principal = Depends(require("email_agent:read"))):
    return list_templates()


@router.get("/templates/{action}/preview")
async def preview_template(action: str, _: Principal = Depends(require("email_agent:read"))):
    """Render a template with dummy data so you can inspect the output."""
    if action not in ACTION_TEMPLATES:
        raise HTTPException(404, f"Unknown action '{action}'")
    from .renderer import render as do_render
    dummy = {
        "candidate_name":  "Jane Doe",
        "candidate_email": "jane@example.com",
        "role_id":         "junior-python-backend",
        "role":            {"title": "Junior Python Backend Developer"},
        "sender_name":     "Hiring Team",
        "org_name":        "Acme Corp",
        # task extras
        "task_title":        "Build a REST API",
        "task_description":  "Create a small FastAPI service…",
        "task_instructions": "1. Fork the repo  2. Implement the endpoints  3. Submit your Drive link",
        "task_deadline":     "2026-10-31",
        # custom extras
        "subject": "Important update",
        "body":    "We have an update for you.",
    }
    try:
        subject, body = do_render(action, dummy)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    return {"action": action, "subject": subject, "body": body}
