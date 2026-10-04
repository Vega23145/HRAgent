from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, Response
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from resumehub.app.core import db
from resumehub.app.core.audit import audit
from resumehub.app.core.deps import Page, Principal, paged, pagination, require
from resumehub.app.core.utils import SLUG_PATTERN, clean_keys, deep_merge

from .schemas import JobRoleBase, JobRoleCreate

router = APIRouter()
RoleId = Annotated[str, Path(pattern=SLUG_PATTERN)]


def _validate(data: dict) -> dict:
    try:
        clean_keys(data)
        return JobRoleBase.model_validate(data).model_dump()  # defaults filled: stored docs stay uniform
    except (ValidationError, ValueError) as e:
        raise HTTPException(422, str(e)) from None


@router.get("")
async def list_roles(
    q: str | None = None,
    department: str | None = None,
    experience_level: str | None = None,
    skill: str | None = None,
    p: Page = Depends(pagination),
    _: Principal = Depends(require("job_roles:read")),
):
    filt: dict[str, Any] = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        filt["$or"] = [{"title": rx}, {"_id": rx}, {"description": rx}]
    if department:
        filt["department"] = department
    if experience_level:
        filt["experience_level"] = experience_level
    if skill:
        filt["required_skills.name"] = skill.strip().lower()
    total = await db.job_roles().count_documents(filt)
    cur = db.job_roles().find(filt).sort("title", 1).skip(p.skip).limit(p.size)
    return paged(await cur.to_list(), total, p)


@router.post("", status_code=201)
async def create_role(body: JobRoleCreate, request: Request, actor: Principal = Depends(require("job_roles:create"))):
    doc = {"_id": body.id, **body.model_dump(exclude={"id"})}
    clean_keys(doc)
    try:
        await db.job_roles().insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "A role with this id already exists") from None
    await audit(actor, "job_roles.create", "job_roles", body.id, {"title": body.title}, request)
    return doc


@router.get("/{role_id}")
async def get_role(role_id: RoleId, _: Principal = Depends(require("job_roles:read"))):
    doc = await db.job_roles().find_one({"_id": role_id})
    if not doc:
        raise HTTPException(404, "Role not found")
    return doc


@router.put("/{role_id}")
async def replace_role(
    role_id: RoleId, request: Request, body: dict[str, Any] = Body(...),
    actor: Principal = Depends(require("job_roles:update")),
):
    if "_id" in body and body["_id"] != role_id:
        raise HTTPException(422, "_id cannot be changed")
    body.pop("_id", None)
    new = _validate(body)
    res = await db.job_roles().replace_one({"_id": role_id}, {"_id": role_id, **new})
    if res.matched_count == 0:
        raise HTTPException(404, "Role not found")
    await audit(actor, "job_roles.replace", "job_roles", role_id, request=request)
    return await db.job_roles().find_one({"_id": role_id})


@router.patch("/{role_id}")
async def patch_role(
    role_id: RoleId, request: Request, body: dict[str, Any] = Body(...),
    actor: Principal = Depends(require("job_roles:update")),
):
    if "_id" in body:
        raise HTTPException(422, "_id cannot be changed")
    if not body:
        raise HTTPException(400, "Nothing to update")
    existing = await db.job_roles().find_one({"_id": role_id})
    if not existing:
        raise HTTPException(404, "Role not found")
    existing.pop("_id")
    merged = _validate(deep_merge(existing, body))
    await db.job_roles().replace_one({"_id": role_id}, {"_id": role_id, **merged})
    await audit(actor, "job_roles.update", "job_roles", role_id, {"fields": sorted(body)}, request)
    return await db.job_roles().find_one({"_id": role_id})


@router.delete("/{role_id}", status_code=204)
async def delete_role(
    role_id: RoleId, request: Request, purge_matches: bool = False,
    actor: Principal = Depends(require("job_roles:delete")),
):
    """``purge_matches=true`` also removes ``match.<role_id>`` from every resume."""
    if purge_matches and not actor.can("matching:manage"):
        raise HTTPException(403, "Missing permission: matching:manage")
    res = await db.job_roles().delete_one({"_id": role_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Role not found")
    purged = 0
    if purge_matches:  # slug ids contain no dots or $, so the field path is safe
        r = await db.resumes().update_many({f"match.{role_id}": {"$exists": True}}, {"$unset": {f"match.{role_id}": ""}})
        purged = r.modified_count
    await audit(actor, "job_roles.delete", "job_roles", role_id, {"purged_matches": purged}, request)
    return Response(status_code=204)
