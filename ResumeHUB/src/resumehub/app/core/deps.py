from __future__ import annotations

from dataclasses import dataclass, field

import jwt
from fastapi import Depends, HTTPException, Query, Request
from fastapi.security import OAuth2PasswordBearer

from . import db
from .config import API_PREFIX, get_settings
from .permissions import is_allowed
from .security import decode_token

oauth2 = OAuth2PasswordBearer(tokenUrl=f"{API_PREFIX}/auth/login", auto_error=False)


@dataclass
class Principal:
    id: str
    email: str
    full_name: str | None
    roles: list[str]
    allow: set[str] = field(default_factory=set)
    deny: set[str] = field(default_factory=set)

    def can(self, perm: str) -> bool:
        return is_allowed(perm, self.allow, self.deny)


async def build_principal(user: dict) -> Principal:
    role_names = list(user.get("roles", []))
    docs = await db.access_roles().find({"_id": {"$in": role_names}}).to_list()
    allow = {p for r in docs for p in r.get("permissions", [])} | set(user.get("grants", []))
    return Principal(
        id=user["_id"],
        email=user["email"],
        full_name=user.get("full_name"),
        roles=role_names,
        allow=allow,
        deny=set(user.get("denies", [])),
    )


async def get_principal(token: str | None = Depends(oauth2)) -> Principal:
    unauth = HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    if not token:
        raise unauth
    try:
        payload = decode_token(get_settings(), token, "access")
    except jwt.PyJWTError:
        raise unauth from None
    user = await db.users().find_one({"_id": payload["sub"]})
    if not user or not user.get("is_active") or user.get("token_version", 0) != payload["ver"]:
        raise unauth
    return await build_principal(user)


def require(*perms: str):
    """Dependency factory: the caller must hold *all* listed permissions."""

    async def dep(principal: Principal = Depends(get_principal)) -> Principal:
        missing = [p for p in perms if not principal.can(p)]
        if missing:
            raise HTTPException(403, f"Missing permission: {', '.join(missing)}")
        return principal

    return dep


def get_ctx(request: Request):
    return request.app.state.ctx


@dataclass
class Page:
    page: int
    size: int

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.size


def pagination(page: int = Query(1, ge=1, le=100000), size: int = Query(20, ge=1, le=100)) -> Page:
    return Page(page, size)


def paged(items: list, total: int, p: Page) -> dict:
    return {"items": items, "total": total, "page": p.page, "size": p.size}
