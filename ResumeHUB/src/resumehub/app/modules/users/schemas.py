from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from resumehub.app.core.permissions import PERM_PATTERN
from resumehub.app.core.utils import SLUG_PATTERN

Perm = Annotated[str, StringConstraints(pattern=PERM_PATTERN, max_length=64)]
RoleName = Annotated[str, StringConstraints(pattern=SLUG_PATTERN)]
Email = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)]


def _dedupe(v: list[str]) -> list[str]:
    return sorted(set(v))


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email
    full_name: str | None = Field(None, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    is_active: bool = True
    roles: list[RoleName] = []
    grants: list[Perm] = []
    denies: list[Perm] = []

    _norm = field_validator("roles", "grants", "denies")(_dedupe)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email | None = None
    full_name: str | None = Field(None, max_length=120)
    password: str | None = Field(None, min_length=12, max_length=128)
    is_active: bool | None = None
    roles: list[RoleName] | None = None
    grants: list[Perm] | None = None
    denies: list[Perm] | None = None

    @field_validator("roles", "grants", "denies")
    @classmethod
    def _norm(cls, v):
        return _dedupe(v) if v is not None else v

    @field_validator("email")
    @classmethod
    def _lower(cls, v):
        return v.strip().lower() if v else v


class AccessRoleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    name: RoleName = Field(alias="_id")
    description: str = Field("", max_length=300)
    permissions: list[Perm] = []

    _norm = field_validator("permissions")(_dedupe)


class AccessRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str | None = Field(None, max_length=300)
    permissions: list[Perm] | None = None

    @field_validator("permissions")
    @classmethod
    def _norm(cls, v):
        return _dedupe(v) if v is not None else v
