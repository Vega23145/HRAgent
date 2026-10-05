from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from resumehub.app.core import db
from resumehub.app.core.config import Settings, get_settings
from resumehub.app.core.loader import build_context, discover, mount_modules, shutdown_modules, startup_modules

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

ADMIN_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)
FRONTEND_ORIGIN = "https://frontend.1shhub.com"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    modules = discover(settings)
    ctx = build_context(settings, modules)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.validate_for_env()
        await db.connect(settings)
        try:
            await startup_modules(ctx, modules)
            yield
        finally:
            await shutdown_modules(ctx, modules)
            await db.disconnect()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.state.ctx = ctx

    cors_origins = list(dict.fromkeys([*settings.cors_origins, FRONTEND_ORIGIN]))
    if cors_origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=cors_origins, allow_credentials=False,
            allow_methods=["*"], allow_headers=["Authorization", "Content-Type"],
        )

    @app.middleware("http")
    async def security_headers(request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/admin"):
            resp.headers["Content-Security-Policy"] = ADMIN_CSP
            resp.headers["X-Frame-Options"] = "DENY"
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz():
        try:
            await db.get_db().command("ping")
        except Exception:  # noqa: BLE001
            return JSONResponse({"status": "database unavailable"}, status_code=503)
        return {"status": "ready", "modules": sorted(ctx.modules)}

    mount_modules(app, modules)
    return app


app = create_app()
