from __future__ import annotations

import importlib
import logging
import pkgutil
from importlib.metadata import entry_points

from fastapi import FastAPI

from .config import API_PREFIX, Settings
from .plugin import AppContext, Module

log = logging.getLogger("hub.loader")
ALWAYS_ON = {"auth", "users"}


def _as_module(obj) -> Module | None:
    if isinstance(obj, type) and issubclass(obj, Module):
        obj = obj()
    return obj if isinstance(obj, Module) else None


def discover(settings: Settings) -> list[Module]:
    found: dict[str, Module] = {}
    package = f"{__package__.rsplit('.', 1)[0]}.modules"
    pkg = importlib.import_module(package)
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{package}.{info.name}")
        inst = _as_module(getattr(mod, "module", None))
        if inst:
            found[inst.name] = inst
    for ep in entry_points(group="resume_hub.modules"):
        inst = _as_module(ep.load())
        if inst:
            found[inst.name] = inst

    if settings.enabled_modules is not None:
        keep = set(settings.enabled_modules) | ALWAYS_ON
        found = {n: m for n, m in found.items() if n in keep}
    return _order(found)


def _order(mods: dict[str, Module]) -> list[Module]:
    ordered: list[Module] = []
    state: dict[str, int] = {}

    def visit(name: str, chain: list[str]) -> None:
        if state.get(name) == 2:
            return
        if state.get(name) == 1:
            raise RuntimeError("circular module dependency: " + " -> ".join(chain + [name]))
        mod = mods.get(name)
        if mod is None:
            raise RuntimeError(f"module '{chain[-1]}' depends on missing or disabled module '{name}'")
        state[name] = 1
        for dep in mod.depends_on:
            visit(dep, chain + [name])
        state[name] = 2
        ordered.append(mod)

    for name in sorted(mods):
        visit(name, [])
    return ordered


def build_context(settings: Settings, modules: list[Module]) -> AppContext:
    ctx = AppContext(settings=settings)
    for m in modules:
        ctx.modules[m.name] = m
        for key, desc in m.permissions.items():
            ctx.permissions[key] = desc
            ctx.permission_owner[key] = m.name
    return ctx


def mount_modules(app: FastAPI, modules: list[Module]) -> None:
    for m in modules:
        router = m.router()
        if router is not None:
            app.include_router(router, prefix=f"{API_PREFIX}{m.mount_prefix}", tags=[m.name])
    for m in modules:  # raw mounts last so they never shadow API routes
        for path, asgi_app, name in m.mounts():
            app.mount(path, asgi_app, name=name)


async def startup_modules(ctx: AppContext, modules: list[Module]) -> None:
    for m in modules:
        await m.ensure_indexes(ctx)
    for m in modules:
        await m.on_startup(ctx)
        log.info("module started: %s %s", m.name, m.version)


async def shutdown_modules(ctx: AppContext, modules: list[Module]) -> None:
    for m in reversed(modules):
        try:
            await m.on_shutdown(ctx)
        except Exception:  # noqa: BLE001
            log.exception("module %s failed to shut down cleanly", m.name)
