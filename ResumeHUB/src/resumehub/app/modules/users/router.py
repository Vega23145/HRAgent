from __future__ import annotations

import re
import uuid
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pymongo.errors import DuplicateKeyError

from resumehub.app.core import db
from resumehub.app.core.audit import audit
from resumehub.app.core.deps import Page, Principal, get_ctx, paged, pagination, require
from resumehub.app.core.security import hash_password
from resumehub.app.core.utils import utcnow

from .schemas import AccessRoleCreate, AccessRoleUpdate, UserCreate, UserUpdate

router = APIRouter()


def public_user(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "password_hash"}


def _rx(q: str) -> dict:
    return {"$regex": re.escape(q), "$options": "i"}


# ---- privilege helpers ------------------------------------------------------------

def _holds_all(actor: Principal, perms: Iterable[str]) -> list[str]:
    """Returns the permissions the actor does NOT hold (empty list = holds all)."""
    return sorted(p for p in set(perms) if not actor.can(p))


async def _perms_of_user(doc: dict) -> set[str]:
    roles = await db.access_roles().find({"_id": {"$in": doc.get("roles", [])}}).to_list()
    return {p for r in roles for p in r.get("permissions", [])} | set(doc.get("grants", []))


async def _check_assignable(actor: Principal, roles: Iterable[str], grants: Iterable[str]) -> None:
    roles = list(roles)
    perms: set[str] = set(grants)
    if roles:
        docs = await db.access_roles().find({"_id": {"$in": roles}}).to_list()
        missing = set(roles) - {d["_id"] for d in docs}
        if missing:
            raise HTTPException(422, f"Unknown role(s): {', '.join(sorted(missing))}")
        perms |= {p for d in docs for p in d.get("permissions", [])}
    lacking = _holds_all(actor, perms)
    if lacking:
        raise HTTPException(403, "You cannot grant permissions you do not hold: " + ", ".join(lacking[:5]))


async def _super_role_names() -> set[str]:
    return {r["_id"] async for r in db.access_roles().find({"permissions": "*"}, {"_id": 1})}


def _is_super(roles: Iterable[str], grants: Iterable[str], active: bool, super_roles: set[str]) -> bool:
    return active and (bool(set(roles) & super_roles) or "*" in set(grants))


async def _other_supers(exclude_id: str, super_roles: set[str]) -> int:
    return await db.users().count_documents(
        {
            "_id": {"$ne": exclude_id},
            "is_active": True,
            "$or": [{"roles": {"$in": list(super_roles)}}, {"grants": "*"}],
        }
    )


async def _require_outranks(actor: Principal, target: dict) -> None:
    lacking = _holds_all(actor, await _perms_of_user(target))
    if lacking:
        raise HTTPException(403, "Target user holds permissions you do not have")


# ---- users ------------------------------------------------------------------------

@router.get("/users")
async def list_users(
    q: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    p: Page = Depends(pagination),
    _: Principal = Depends(require("users:read")),
):
    filt: dict = {}
    if q:
        filt["$or"] = [{"email": _rx(q)}, {"full_name": _rx(q)}]
    if role:
        filt["roles"] = role
    if is_active is not None:
        filt["is_active"] = is_active
    total = await db.users().count_documents(filt)
    cur = db.users().find(filt, {"password_hash": 0}).sort("email", 1).skip(p.skip).limit(p.size)
    return paged(await cur.to_list(), total, p)


@router.post("/users", status_code=201)
async def create_user(body: UserCreate, request: Request, actor: Principal = Depends(require("users:create"))):
    if (body.roles or body.grants or body.denies) and not actor.can("users:assign"):
        raise HTTPException(403, "Missing permission: users:assign")
    await _check_assignable(actor, body.roles, body.grants)
    now = utcnow()
    doc = {
        "_id": uuid.uuid4().hex,
        "email": body.email,
        "full_name": body.full_name,
        "password_hash": hash_password(body.password),
        "is_active": body.is_active,
        "roles": body.roles,
        "grants": body.grants,
        "denies": body.denies,
        "token_version": 0,
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db.users().insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "A user with this email already exists") from None
    await audit(actor, "users.create", "users", doc["_id"], {"email": doc["email"], "roles": body.roles}, request)
    return public_user(doc)


@router.get("/users/{user_id}")
async def get_user(user_id: str, _: Principal = Depends(require("users:read"))):
    doc = await db.users().find_one({"_id": user_id}, {"password_hash": 0})
    if not doc:
        raise HTTPException(404, "User not found")
    return doc


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: UserUpdate, request: Request, actor: Principal = Depends(require("users:update"))):
    doc = await db.users().find_one({"_id": user_id})
    if not doc:
        raise HTTPException(404, "User not found")
    sent = body.model_fields_set
    is_self = actor.id == user_id
    priv_fields = sent & {"roles", "grants", "denies"}

    if priv_fields and not actor.can("users:assign"):
        raise HTTPException(403, "Missing permission: users:assign")
    if is_self and (priv_fields or "is_active" in sent):
        raise HTTPException(403, "You cannot change your own roles, permissions or status")
    if not is_self:
        await _require_outranks(actor, doc)

    new_roles = body.roles if "roles" in sent and body.roles is not None else doc.get("roles", [])
    new_grants = body.grants if "grants" in sent and body.grants is not None else doc.get("grants", [])
    await _check_assignable(
        actor,
        set(new_roles) - set(doc.get("roles", [])),
        set(new_grants) - set(doc.get("grants", [])),
    )

    new_active = body.is_active if "is_active" in sent and body.is_active is not None else doc.get("is_active", True)
    supers = await _super_role_names()
    was = _is_super(doc.get("roles", []), doc.get("grants", []), doc.get("is_active", True), supers)
    will = _is_super(new_roles, new_grants, new_active, supers)
    if was and not will and await _other_supers(user_id, supers) == 0:
        raise HTTPException(409, "This would remove the last active administrator")

    sets: dict = {}
    for f in ("email", "full_name", "is_active", "roles", "grants", "denies"):
        if f in sent and getattr(body, f) is not None or (f == "full_name" and f in sent):
            sets[f] = getattr(body, f)
    update: dict = {}
    if "password" in sent and body.password:
        sets["password_hash"] = hash_password(body.password)
        update["$inc"] = {"token_version": 1}
    if not sets:
        raise HTTPException(400, "Nothing to update")
    sets["updated_at"] = utcnow()
    update["$set"] = sets
    try:
        await db.users().update_one({"_id": user_id}, update)
    except DuplicateKeyError:
        raise HTTPException(409, "A user with this email already exists") from None
    changed = sorted(k for k in sets if k not in ("updated_at", "password_hash")) + (["password"] if "password_hash" in sets else [])
    await audit(actor, "users.update", "users", user_id, {"fields": changed}, request)
    return await db.users().find_one({"_id": user_id}, {"password_hash": 0})


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: str, request: Request, actor: Principal = Depends(require("users:delete"))):
    if actor.id == user_id:
        raise HTTPException(403, "You cannot delete your own account")
    doc = await db.users().find_one({"_id": user_id})
    if not doc:
        raise HTTPException(404, "User not found")
    await _require_outranks(actor, doc)
    supers = await _super_role_names()
    if _is_super(doc.get("roles", []), doc.get("grants", []), doc.get("is_active", True), supers) \
            and await _other_supers(user_id, supers) == 0:
        raise HTTPException(409, "This would remove the last active administrator")
    await db.users().delete_one({"_id": user_id})
    await audit(actor, "users.delete", "users", user_id, {"email": doc["email"]}, request)
    return Response(status_code=204)


# ---- access roles -----------------------------------------------------------------

@router.get("/access-roles")
async def list_access_roles(
    q: str | None = None,
    p: Page = Depends(pagination),
    _: Principal = Depends(require("access_roles:read")),
):
    filt = {"$or": [{"_id": _rx(q)}, {"description": _rx(q)}]} if q else {}
    total = await db.access_roles().count_documents(filt)
    cur = db.access_roles().find(filt).sort("_id", 1).skip(p.skip).limit(p.size)
    return paged(await cur.to_list(), total, p)


@router.post("/access-roles", status_code=201)
async def create_access_role(body: AccessRoleCreate, request: Request, actor: Principal = Depends(require("access_roles:create"))):
    lacking = _holds_all(actor, body.permissions)
    if lacking:
        raise HTTPException(403, "You cannot grant permissions you do not hold: " + ", ".join(lacking[:5]))
    now = utcnow()
    doc = {"_id": body.name, "description": body.description, "permissions": body.permissions,
           "builtin": False, "created_at": now, "updated_at": now}
    try:
        await db.access_roles().insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "Role already exists") from None
    await audit(actor, "access_roles.create", "access_roles", body.name, {"permissions": body.permissions}, request)
    return doc


@router.get("/access-roles/{name}")
async def get_access_role(name: str, _: Principal = Depends(require("access_roles:read"))):
    doc = await db.access_roles().find_one({"_id": name})
    if not doc:
        raise HTTPException(404, "Role not found")
    return doc


@router.patch("/access-roles/{name}")
async def update_access_role(name: str, body: AccessRoleUpdate, request: Request, actor: Principal = Depends(require("access_roles:update"))):
    doc = await db.access_roles().find_one({"_id": name})
    if not doc:
        raise HTTPException(404, "Role not found")
    sent = body.model_fields_set
    if name == "admin" and "permissions" in sent:
        raise HTTPException(403, "The admin role's permissions are fixed to '*'")
    if _holds_all(actor, doc.get("permissions", [])):
        raise HTTPException(403, "This role holds permissions you do not have")
    sets: dict = {}
    if "description" in sent and body.description is not None:
        sets["description"] = body.description
    if "permissions" in sent and body.permissions is not None:
        lacking = _holds_all(actor, body.permissions)
        if lacking:
            raise HTTPException(403, "You cannot grant permissions you do not hold: " + ", ".join(lacking[:5]))
        sets["permissions"] = body.permissions
    if not sets:
        raise HTTPException(400, "Nothing to update")
    sets["updated_at"] = utcnow()
    await db.access_roles().update_one({"_id": name}, {"$set": sets})
    await audit(actor, "access_roles.update", "access_roles", name, {"fields": sorted(k for k in sets if k != "updated_at")}, request)
    return await db.access_roles().find_one({"_id": name})


@router.delete("/access-roles/{name}", status_code=204)
async def delete_access_role(name: str, request: Request, actor: Principal = Depends(require("access_roles:delete"))):
    doc = await db.access_roles().find_one({"_id": name})
    if not doc:
        raise HTTPException(404, "Role not found")
    if doc.get("builtin"):
        raise HTTPException(403, "Built-in roles cannot be deleted")
    if _holds_all(actor, doc.get("permissions", [])):
        raise HTTPException(403, "This role holds permissions you do not have")
    in_use = await db.users().count_documents({"roles": name})
    if in_use:
        raise HTTPException(409, f"Role is assigned to {in_use} user(s)")
    await db.access_roles().delete_one({"_id": name})
    await audit(actor, "access_roles.delete", "access_roles", name, request=request)
    return Response(status_code=204)


@router.get("/permissions")
async def permission_catalog(request: Request, _: Principal = Depends(require("access_roles:read"))):
    ctx = get_ctx(request)
    return [
        {"key": k, "description": d, "module": ctx.permission_owner.get(k)}
        for k, d in sorted(ctx.permissions.items())
    ]
