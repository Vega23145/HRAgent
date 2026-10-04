from __future__ import annotations

import time
from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from resumehub.app.core import db
from resumehub.app.core.audit import audit
from resumehub.app.core.config import Settings, get_settings
from resumehub.app.core.deps import Principal, get_ctx, get_principal
from resumehub.app.core.permissions import effective
from resumehub.app.core.security import (
    create_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from resumehub.app.core.utils import utcnow

router = APIRouter()

# Per-process throttle. Behind several workers, also rate-limit at the gateway.
_failures: dict[str, list[float]] = {}


def _throttled(key: str, s: Settings) -> bool:
    now = time.monotonic()
    hits = [t for t in _failures.get(key, []) if now - t < s.login_window_sec]
    _failures[key] = hits
    return len(hits) >= s.login_max_attempts


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshIn(BaseModel):
    refresh_token: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)


def _pair(s: Settings, user: dict) -> TokenPair:
    ver = user.get("token_version", 0)
    access = create_token(s, sub=user["_id"], kind="access", ttl=timedelta(minutes=s.access_ttl_min), ver=ver)
    refresh = create_token(s, sub=user["_id"], kind="refresh", ttl=timedelta(days=s.refresh_ttl_days), ver=ver)
    return TokenPair(access_token=access, refresh_token=refresh, expires_in=s.access_ttl_min * 60)


@router.post("/login", response_model=TokenPair)
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    s = get_settings()
    email = form.username.strip().lower()
    ip = request.client.host if request.client else "?"
    key = f"{ip}|{email}"
    if _throttled(key, s):
        raise HTTPException(429, "Too many failed attempts; try again later")

    user = await db.users().find_one({"email": email})
    ok = verify_password(user.get("password_hash") if user else None, form.password)
    if not (ok and user and user.get("is_active")):
        _failures.setdefault(key, []).append(time.monotonic())
        await audit(None, "auth.login_failed", "auth", detail={"email": email}, request=request)
        raise HTTPException(401, "Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})

    _failures.pop(key, None)
    update: dict = {"last_login": utcnow()}
    if needs_rehash(user["password_hash"]):
        update["password_hash"] = hash_password(form.password)
    await db.users().update_one({"_id": user["_id"]}, {"$set": update})
    return _pair(s, user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshIn):
    s = get_settings()
    bad = HTTPException(401, "Invalid refresh token")
    try:
        payload = decode_token(s, body.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise bad from None
    user = await db.users().find_one({"_id": payload["sub"]})
    if not user or not user.get("is_active") or user.get("token_version", 0) != payload["ver"]:
        raise bad
    return _pair(s, user)


@router.post("/logout", status_code=204)
async def logout(request: Request, principal: Principal = Depends(get_principal)):
    """Revokes every access/refresh token issued to this user."""
    await db.users().update_one({"_id": principal.id}, {"$inc": {"token_version": 1}})
    await audit(principal, "auth.logout", "users", principal.id, request=request)
    return Response(status_code=204)


@router.post("/change-password", status_code=204)
async def change_password(body: PasswordChange, request: Request, principal: Principal = Depends(get_principal)):
    user = await db.users().find_one({"_id": principal.id})
    if not user or not verify_password(user.get("password_hash"), body.current_password):
        raise HTTPException(400, "Current password is incorrect")
    await db.users().update_one(
        {"_id": principal.id},
        {"$set": {"password_hash": hash_password(body.new_password), "updated_at": utcnow()}, "$inc": {"token_version": 1}},
    )
    await audit(principal, "auth.password_changed", "users", principal.id, request=request)
    return Response(status_code=204)


@router.get("/me")
async def me(request: Request, principal: Principal = Depends(get_principal)):
    ctx = get_ctx(request)
    return {
        "id": principal.id,
        "email": principal.email,
        "full_name": principal.full_name,
        "roles": principal.roles,
        "permissions": effective(ctx.permissions, principal.allow, principal.deny),
        "allow": sorted(principal.allow),
        "deny": sorted(principal.deny),
    }
