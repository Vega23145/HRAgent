from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import Request

from . import db
from .utils import utcnow

log = logging.getLogger("hub.audit")


async def audit(
    actor,
    action: str,
    resource: str,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """Append-only audit trail. Never include secrets in ``detail``; never fails the request."""
    doc = {
        "_id": uuid.uuid4().hex,
        "ts": utcnow(),
        "actor_id": getattr(actor, "id", None),
        "actor_email": getattr(actor, "email", None),
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "detail": detail or {},
        "ip": request.client.host if request is not None and request.client else None,
    }
    try:
        await db.audit_log().insert_one(doc)
    except Exception:  # noqa: BLE001
        log.exception("failed to write audit record %s %s", action, resource)
