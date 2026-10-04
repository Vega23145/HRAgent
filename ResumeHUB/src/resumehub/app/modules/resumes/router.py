from __future__ import annotations

import re
import uuid
from pathlib import Path as FsPath
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from resumehub.app.core import db
from resumehub.app.core.audit import audit
from resumehub.app.core.config import get_settings
from resumehub.app.core.deps import Page, Principal, paged, pagination, require
from resumehub.app.core.utils import SLUG_PATTERN, build_set, clean_keys, deep_merge

from .schemas import RESUME_ID_RE, ResumeCreate, ResumeDoc

router = APIRouter()
RoleId = Annotated[str, Path(pattern=SLUG_PATTERN)]
PII_TOUCHING = {"contact", "email", "body"}


def _pii_ok(actor: Principal) -> bool:
    return actor.can("resumes:read_pii")


def redact(doc: dict) -> dict:
    """Strips contact details, the raw mail body and sender/message-id."""
    doc = dict(doc)
    doc.pop("contact", None)
    doc.pop("body", None)
    if isinstance(doc.get("email"), dict):
        doc["email"] = {k: v for k, v in doc["email"].items() if k not in ("sender", "message_id")}
    doc["_redacted"] = True
    return doc


def _out(doc: dict, actor: Principal) -> dict:
    return doc if _pii_ok(actor) else redact(doc)


def _check_id(resume_id: str) -> None:
    if not RESUME_ID_RE.match(resume_id):
        raise HTTPException(404, "Resume not found")


def _validate(data: dict) -> dict:
    try:
        clean_keys(data)
        ResumeDoc.model_validate(data)
    except (ValidationError, ValueError) as e:
        raise HTTPException(422, str(e)) from None
    return data


def _reject_managed(data: dict) -> None:
    for k in ("_id", "match"):
        if k in data:
            raise HTTPException(422, f"'{k}' cannot be set through this endpoint")


def _summary(doc: dict, pii: bool) -> dict:
    out = {
        "_id": doc["_id"],
        "name": (doc.get("resume") or {}).get("name"),
        "subject": (doc.get("email") or {}).get("subject"),
        "date": (doc.get("email") or {}).get("date"),
        "resume_file": doc.get("resume_file"),
        "scores": {r: m.get("score") for r, m in (doc.get("match") or {}).items() if isinstance(m, dict)},
    }
    if pii:
        out["sender"] = (doc.get("email") or {}).get("sender")
    return out


@router.get("")
async def list_resumes(
    q: str | None = Query(None, max_length=100, description="name / subject (and sender/contact with PII access)"),
    skill: str | None = Query(None, max_length=60),
    role: Annotated[str | None, Query(pattern=SLUG_PATTERN)] = None,
    min_score: float | None = Query(None, ge=0, le=100),
    has_match: bool | None = None,
    sort: Literal["_id", "name", "-name", "score", "-score"] = "_id",
    p: Page = Depends(pagination),
    actor: Principal = Depends(require("resumes:read")),
):
    pii = _pii_ok(actor)
    filt: dict[str, Any] = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        ors = [{"resume.name": rx}, {"email.subject": rx}]
        if pii:  # searching PII fields would otherwise be a redaction oracle
            ors += [{"email.sender": rx}, {"contact.emails": rx}]
        filt["$or"] = ors
    if skill:
        filt["resume.skills.items"] = {"$regex": f"^{re.escape(skill)}$", "$options": "i"}
    if (min_score is not None or sort in ("score", "-score")) and not role:
        raise HTTPException(422, "'role' is required with min_score or score sorting")
    if role and min_score is not None:
        filt[f"match.{role}.score"] = {"$gte": min_score}
    if has_match is not None:
        filt["match"] = {"$exists": True, "$ne": {}} if has_match else {"$in": [None, {}]}

    spec = {
        "_id": [("_id", 1)],
        "name": [("resume.name", 1), ("_id", 1)],
        "-name": [("resume.name", -1), ("_id", 1)],
        "score": [(f"match.{role}.score", 1), ("_id", 1)],
        "-score": [(f"match.{role}.score", -1), ("_id", 1)],
    }[sort]
    proj = {"resume.name": 1, "email.subject": 1, "email.date": 1, "email.sender": 1, "resume_file": 1, "match": 1}
    total = await db.resumes().count_documents(filt)
    docs = await db.resumes().find(filt, proj).sort(spec).skip(p.skip).limit(p.size).to_list()
    return paged([_summary(d, pii) for d in docs], total, p)


@router.post("", status_code=201)
async def create_resume(body: ResumeCreate, request: Request, actor: Principal = Depends(require("resumes:create"))):
    data = body.model_dump(exclude_unset=True, exclude={"id"})
    _reject_managed(data)
    clean_keys(data)
    if not _pii_ok(actor) and PII_TOUCHING & data.keys():
        raise HTTPException(403, "Missing permission: resumes:read_pii (required to write contact/email/body)")
    doc = {"_id": body.id or uuid.uuid4().hex[:16], **data}
    try:
        await db.resumes().insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "Resume already exists (duplicate _id or email.message_id)") from None
    await audit(actor, "resumes.create", "resumes", doc["_id"], request=request)
    return _out(doc, actor)


@router.get("/{resume_id}")
async def get_resume(resume_id: str, actor: Principal = Depends(require("resumes:read"))):
    _check_id(resume_id)
    doc = await db.resumes().find_one({"_id": resume_id})
    if not doc:
        raise HTTPException(404, "Resume not found")
    return _out(doc, actor)


@router.put("/{resume_id}")
async def replace_resume(
    resume_id: str, request: Request, body: dict[str, Any] = Body(...),
    actor: Principal = Depends(require("resumes:update")),
):
    """Replaces everything except ``_id`` and the matcher-owned ``match`` block."""
    _check_id(resume_id)
    if not _pii_ok(actor):
        raise HTTPException(403, "Missing permission: resumes:read_pii (a full replace can overwrite contact data)")
    _reject_managed(body)
    _validate(body)
    existing = await db.resumes().find_one({"_id": resume_id}, {"match": 1})
    if not existing:
        raise HTTPException(404, "Resume not found")
    new = {"_id": resume_id, **body}
    if "match" in existing:
        new["match"] = existing["match"]
    await db.resumes().replace_one({"_id": resume_id}, new)
    await audit(actor, "resumes.replace", "resumes", resume_id, request=request)
    return _out(await db.resumes().find_one({"_id": resume_id}), actor)


@router.patch("/{resume_id}")
async def patch_resume(
    resume_id: str, request: Request, body: dict[str, Any] = Body(...),
    actor: Principal = Depends(require("resumes:update")),
):
    """Deep-merges objects; lists and scalars are replaced."""
    _check_id(resume_id)
    _reject_managed(body)
    if not body:
        raise HTTPException(400, "Nothing to update")
    if not _pii_ok(actor) and PII_TOUCHING & body.keys():
        raise HTTPException(403, "Missing permission: resumes:read_pii (required to write contact/email/body)")
    existing = await db.resumes().find_one({"_id": resume_id})
    if not existing:
        raise HTTPException(404, "Resume not found")
    clean_keys(body)
    plain = {k: v for k, v in existing.items() if k not in ("_id", "match")}
    _validate(deep_merge(plain, body))
    await db.resumes().update_one({"_id": resume_id}, {"$set": build_set(existing, body)})
    await audit(actor, "resumes.update", "resumes", resume_id, {"fields": sorted(body)}, request)
    return _out(await db.resumes().find_one({"_id": resume_id}), actor)


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(resume_id: str, request: Request, actor: Principal = Depends(require("resumes:delete"))):
    _check_id(resume_id)
    res = await db.resumes().delete_one({"_id": resume_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Resume not found")
    await audit(actor, "resumes.delete", "resumes", resume_id, request=request)
    return Response(status_code=204)


@router.get("/{resume_id}/file")
async def download_resume_file(resume_id: str, request: Request, actor: Principal = Depends(require("resumes:download"))):
    _check_id(resume_id)
    base = get_settings().resume_files_dir
    if not base:
        raise HTTPException(501, "HUB_RESUME_FILES_DIR is not configured")
    doc = await db.resumes().find_one({"_id": resume_id}, {"resume_file": 1})
    if not doc or not doc.get("resume_file"):
        raise HTTPException(404, "No file for this resume")
    root = FsPath(base).resolve()
    path = (root / doc["resume_file"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "File not found on disk")
    await audit(actor, "resumes.download", "resumes", resume_id, request=request)
    return FileResponse(path, filename=path.name, content_disposition_type="attachment")
