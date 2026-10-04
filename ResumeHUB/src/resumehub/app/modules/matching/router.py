from __future__ import annotations

import logging
import uuid
from functools import partial
from typing import Annotated

import anyio.to_thread
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Request, Response

from resumehub.app.core import db
from resumehub.app.core.audit import audit
from resumehub.app.core.deps import Page, Principal, paged, pagination, require
from resumehub.app.core.utils import SLUG_PATTERN, jsonable, utcnow

from . import adapter

log = logging.getLogger("hub.matching")
router = APIRouter()
RoleId = Annotated[str, Path(pattern=SLUG_PATTERN)]


async def _ensure_exist(resume_id: str | None, role_id: str | None) -> None:
    if resume_id is not None and not await db.resumes().find_one({"_id": resume_id}, {"_id": 1}):
        raise HTTPException(404, "Resume not found")
    if role_id is not None and not await db.job_roles().find_one({"_id": role_id}, {"_id": 1}):
        raise HTTPException(404, "Job role not found")


# ---- single match (synchronous) -----------------------------------------------------

@router.post("/resumes/{resume_id}/roles/{role_id}")
async def match_single(resume_id: str, role_id: RoleId, request: Request, actor: Principal = Depends(require("matching:run"))):
    await _ensure_exist(resume_id, role_id)
    try:
        result = await anyio.to_thread.run_sync(adapter.run_one, resume_id, role_id)
    except adapter.MatcherUnavailable as e:
        raise HTTPException(503, str(e)) from None
    except Exception:  # noqa: BLE001
        log.exception("match_one failed for %s / %s", resume_id, role_id)
        raise HTTPException(502, "The matcher failed; see server logs") from None
    await audit(actor, "matching.run_one", "matching", resume_id, {"role": role_id}, request)
    return {"resume_id": resume_id, "role_id": role_id, "result": jsonable(result)}


# ---- bulk matching (background jobs tracked in Mongo) --------------------------------

async def _create_job(kind: str, role_id: str | None, actor: Principal) -> dict:
    scope = "all" if kind == "all" else f"role:{role_id}"
    conflict: dict = {"status": {"$in": ["queued", "running"]}}
    if scope != "all":
        conflict["scope"] = {"$in": ["all", scope]}
    if await db.match_jobs().find_one(conflict, {"_id": 1}):
        raise HTTPException(409, "A conflicting matching job is already queued or running")
    job = {
        "_id": uuid.uuid4().hex, "kind": kind, "scope": scope, "role_id": role_id,
        "status": "queued", "created_at": utcnow(), "created_by": actor.email,
        "started_at": None, "finished_at": None, "stats": None, "error": None,
    }
    await db.match_jobs().insert_one(job)
    return job


async def _execute(job_id: str, kind: str, role_id: str | None) -> None:
    jobs = db.match_jobs()
    await jobs.update_one({"_id": job_id}, {"$set": {"status": "running", "started_at": utcnow()}})
    fn = adapter.run_all if kind == "all" else partial(adapter.run_role, role_id)
    try:
        stats = jsonable(await anyio.to_thread.run_sync(fn))
        patch = {"status": "done", "stats": stats}
    except adapter.MatcherUnavailable as e:
        patch = {"status": "failed", "error": str(e)}
    except Exception as e:  # noqa: BLE001
        log.exception("matching job %s failed", job_id)
        patch = {"status": "failed", "error": str(e)[:500]}
    patch["finished_at"] = utcnow()
    await jobs.update_one({"_id": job_id}, {"$set": patch})


@router.post("/roles/{role_id}/run", status_code=202)
async def run_role(role_id: RoleId, bg: BackgroundTasks, request: Request, actor: Principal = Depends(require("matching:run_bulk"))):
    await _ensure_exist(None, role_id)
    job = await _create_job("role", role_id, actor)
    bg.add_task(_execute, job["_id"], "role", role_id)
    await audit(actor, "matching.run_role", "matching", role_id, {"job": job["_id"]}, request)
    return job


@router.post("/run-all", status_code=202)
async def run_all(bg: BackgroundTasks, request: Request, actor: Principal = Depends(require("matching:run_bulk"))):
    job = await _create_job("all", None, actor)
    bg.add_task(_execute, job["_id"], "all", None)
    await audit(actor, "matching.run_all", "matching", None, {"job": job["_id"]}, request)
    return job


@router.get("/jobs")
async def list_jobs(status: str | None = None, p: Page = Depends(pagination), _: Principal = Depends(require("matching:read"))):
    filt = {"status": status} if status else {}
    total = await db.match_jobs().count_documents(filt)
    cur = db.match_jobs().find(filt).sort("created_at", -1).skip(p.skip).limit(p.size)
    return paged(await cur.to_list(), total, p)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, _: Principal = Depends(require("matching:read"))):
    job = await db.match_jobs().find_one({"_id": job_id})
    if not job:
        raise HTTPException(404, "Job not found")
    return job


# ---- reading results ----------------------------------------------------------------

@router.get("/resumes/{resume_id}")
async def resume_matches(resume_id: str, _: Principal = Depends(require("matching:read"))):
    doc = await db.resumes().find_one({"_id": resume_id}, {"match": 1})
    if not doc:
        raise HTTPException(404, "Resume not found")
    return {"resume_id": resume_id, "match": doc.get("match") or {}}


@router.get("/roles/{role_id}/leaderboard")
async def leaderboard(
    role_id: RoleId,
    limit: int = Query(25, ge=1, le=200),
    min_score: float = Query(0, ge=0, le=100),
    actor: Principal = Depends(require("matching:read")),
):
    await _ensure_exist(None, role_id)
    key = f"match.{role_id}"  # slug-validated: no dots or operators
    filt = {f"{key}.score": {"$gte": min_score}}
    proj = {"resume.name": 1, key: 1}
    pii = actor.can("resumes:read_pii")
    if pii:
        proj["contact.emails"] = 1
    docs = await db.resumes().find(filt, proj).sort([(f"{key}.score", -1), ("_id", 1)]).limit(limit).to_list()
    items = []
    for d in docs:
        m = d["match"][role_id]
        row = {
            "_id": d["_id"], "name": (d.get("resume") or {}).get("name"), "score": m.get("score"),
            "matched_skills": m.get("matched_skills", []), "missing_skills": m.get("missing_skills", []),
            "breakdown": m.get("breakdown"), "candidate_years": m.get("candidate_years"),
        }
        if pii:
            row["emails"] = (d.get("contact") or {}).get("emails", [])
        items.append(row)
    return {"role_id": role_id, "count": len(items), "items": items}


@router.delete("/resumes/{resume_id}/roles/{role_id}", status_code=204)
async def clear_match(resume_id: str, role_id: RoleId, request: Request, actor: Principal = Depends(require("matching:manage"))):
    res = await db.resumes().update_one({"_id": resume_id, f"match.{role_id}": {"$exists": True}}, {"$unset": {f"match.{role_id}": ""}})
    if res.matched_count == 0:
        raise HTTPException(404, "No stored match for this resume and role")
    await audit(actor, "matching.clear", "matching", resume_id, {"role": role_id}, request)
    return Response(status_code=204)
