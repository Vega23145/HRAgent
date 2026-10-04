from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request

from resumehub.app.core import db
from resumehub.app.core.config import API_PREFIX
from resumehub.app.core.deps import Page, Principal, get_ctx, paged, pagination, require
from resumehub.app.core.permissions import effective

router = APIRouter()


@router.get("/manifest")
async def manifest(request: Request, actor: Principal = Depends(require("admin:access"))):
    """Everything the panel needs: which resources exist and what this user may do with them."""
    ctx = get_ctx(request)
    resources = []
    for m in ctx.modules.values():
        for r in m.admin_resources:
            if not actor.can(r.read):
                continue
            resources.append({
                "key": r.key, "label": r.label, "module": m.name,
                "endpoint": f"{API_PREFIX}{r.endpoint}",
                "columns": [list(c) for c in r.columns],
                "readonly_fields": list(r.readonly_fields),
                "update_method": r.update_method,
                "create_template": r.create_template,
                "description": r.description,
                "can": {
                    "create": bool(r.create and actor.can(r.create)),
                    "update": bool(r.update and actor.can(r.update)),
                    "delete": bool(r.delete and actor.can(r.delete)),
                },
            })
    return {
        "app": ctx.settings.app_name,
        "user": {"email": actor.email, "roles": sorted(actor.roles)},
        "modules": [{"name": m.name, "version": m.version, "description": m.description} for m in ctx.modules.values()],
        "resources": resources,
        "permissions": [
            {"key": k, "description": d, "module": ctx.permission_owner.get(k),
             "granted": k in effective([k], actor.allow, actor.deny)}
            for k, d in sorted(ctx.permissions.items())
        ],
    }


@router.get("/stats")
async def stats(request: Request, _: Principal = Depends(require("admin:access"))):
    ctx = get_ctx(request)
    out: dict = {}
    for m in ctx.modules.values():
        try:
            out.update(await m.stats(ctx))
        except Exception:  # noqa: BLE001 - one broken module must not blank the dashboard
            out[f"{m.name}_error"] = "stats unavailable"
    return out


@router.get("/audit")
async def audit_log(
    q: str | None = None,
    actor_email: str | None = None,
    action: str | None = None,
    p: Page = Depends(pagination),
    _: Principal = Depends(require("admin:audit")),
):
    filt: dict = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        filt["$or"] = [{"actor_email": rx}, {"action": rx}, {"resource": rx}, {"resource_id": rx}]
    if actor_email:
        filt["actor_email"] = actor_email
    if action:
        filt["action"] = action
    total = await db.audit_log().count_documents(filt)
    cur = db.audit_log().find(filt).sort("ts", -1).skip(p.skip).limit(p.size)
    return paged(await cur.to_list(), total, p)


@router.get("/audit/{entry_id}")
async def audit_entry(entry_id: str, _: Principal = Depends(require("admin:audit"))):
    from fastapi import HTTPException

    doc = await db.audit_log().find_one({"_id": entry_id})
    if not doc:
        raise HTTPException(404, "Entry not found")
    return doc
