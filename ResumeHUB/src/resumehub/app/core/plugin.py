"""Plugin contract. A feature module is a package under ``app/modules/<name>/`` whose
``__init__`` exposes a ``module`` attribute (an instance of a ``Module`` subclass).
External packages can register modules via the ``resume_hub.modules`` entry-point group.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from fastapi import APIRouter

from .config import Settings
from .db import get_db


@dataclass(frozen=True)
class AdminResource:
    """Declares a CRUD-able collection so the admin panel can render it with no UI code.

    Contract: GET {endpoint} -> {items,total,page,size}; POST {endpoint};
    GET/PATCH|PUT/DELETE {endpoint}/{id}. ``endpoint`` is relative to the API prefix.
    """

    key: str
    label: str
    endpoint: str
    columns: tuple[tuple[str, str], ...]  # (header, dotted path into a list item)
    read: str
    create: str | None = None
    update: str | None = None
    delete: str | None = None
    update_method: str = "PATCH"
    readonly_fields: tuple[str, ...] = ("_id",)
    create_template: dict | None = None
    description: str = ""


@dataclass
class AppContext:
    settings: Settings
    modules: dict[str, "Module"] = field(default_factory=dict)
    permissions: dict[str, str] = field(default_factory=dict)
    permission_owner: dict[str, str] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)  # inter-module shared objects

    @property
    def db(self):
        return get_db()


class Module:
    name: ClassVar[str]
    version: ClassVar[str] = "1.0.0"
    description: ClassVar[str] = ""
    depends_on: ClassVar[tuple[str, ...]] = ()
    permissions: ClassVar[dict[str, str]] = {}
    admin_resources: ClassVar[tuple[AdminResource, ...]] = ()
    prefix: ClassVar[str | None] = None  # default "/<name>"; "" mounts at the API root

    @property
    def mount_prefix(self) -> str:
        if self.prefix is not None:
            return self.prefix
        return "/" + self.name.replace("_", "-")

    def router(self) -> APIRouter | None:
        """Mounted under /api/v1 + mount_prefix."""
        return None

    def mounts(self) -> list[tuple[str, Any, str]]:
        """Raw ASGI apps (path, app, name) mounted at the root, e.g. static files."""
        return []

    async def ensure_indexes(self, ctx: AppContext) -> None: ...

    async def on_startup(self, ctx: AppContext) -> None: ...

    async def on_shutdown(self, ctx: AppContext) -> None: ...

    async def stats(self, ctx: AppContext) -> dict[str, Any]:
        """Metrics shown on the admin dashboard."""
        return {}
