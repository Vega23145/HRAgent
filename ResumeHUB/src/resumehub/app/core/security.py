from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .config import Settings

_ph = PasswordHasher()
_DUMMY_HASH = _ph.hash("timing-equalizer")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Always performs one argon2 verification, even for unknown users."""
    try:
        return _ph.verify(password_hash or _DUMMY_HASH, password) and bool(password_hash)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _ph.check_needs_rehash(password_hash)


def create_token(settings: Settings, *, sub: str, kind: str, ttl: timedelta, ver: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "typ": kind,
        "ver": ver,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def decode_token(settings: Settings, token: str, kind: str) -> dict:
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_alg],
        options={"require": ["exp", "sub", "typ", "ver"]},
    )
    if payload.get("typ") != kind:
        raise jwt.InvalidTokenError("wrong token type")
    return payload
