"""FastAPI app factory."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from llm_cli.core import dashboard as dash
from llm_cli.core.settings import resolve_settings
from llm_cli.webapi.errors import install_exception_handlers
from llm_cli.webapi.middleware import (
    HostHeaderMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)
from llm_cli.webapi.routes import (
    configs,
    disk,
    doctor,
    health,
    history,
    instance,
    jobs,
    metrics,
    models,
    overview,
    recommendations,
    runtimes,
    settings,
    update,
    version,
)
from llm_cli.webapi.static import mount_spa


def _dist_dir() -> Path:
    try:
        return dash.dist_dir()
    except RuntimeError:
        return Path.cwd() / "dashboard" / "dist"


def create_app(
    *, allowed_hosts: set[str] | None = None, cors_origins: list[str] | None = None
) -> FastAPI:
    if allowed_hosts is None:
        env_val = os.environ.get(
            "LLM_DASHBOARD_ALLOWED_HOSTS", "127.0.0.1:7878,localhost:7878"
        )
        allowed_hosts = {h.strip() for h in env_val.split(",") if h.strip()}
    if cors_origins is None:
        cors_origins = [f"http://{h}" for h in allowed_hosts] + [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]

    app = FastAPI(
        title="LocalLLM Dashboard API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )

    install_exception_handlers(app)

    insecure = os.environ.get("LLM_DASHBOARD_INSECURE") == "1"
    app.add_middleware(SecurityHeadersMiddleware, insecure=insecure)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or [],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(HostHeaderMiddleware, allowed_hosts=allowed_hosts)
    app.add_middleware(RequestIDMiddleware)

    api = FastAPI(title="api")
    install_exception_handlers(api)
    api.include_router(configs.router)
    api.include_router(disk.router)
    api.include_router(doctor.router)
    api.include_router(health.router)
    api.include_router(history.router)
    api.include_router(instance.router)
    api.include_router(jobs.router)
    api.include_router(metrics.router)
    api.include_router(models.router)
    api.include_router(overview.router)
    api.include_router(recommendations.router)
    api.include_router(runtimes.router)
    api.include_router(settings.router)
    api.include_router(update.router)
    api.include_router(version.router)
    app.mount("/api", api)

    @app.get("/docs/dashboard-security", include_in_schema=False)
    def dashboard_security_doc():
        settings = resolve_settings()
        if settings.repo_root is None:
            return PlainTextResponse("repo_root not configured", status_code=503)
        doc_path = settings.repo_root / "docs" / "DASHBOARD-SECURITY.md"
        return PlainTextResponse(doc_path.read_text(encoding="utf-8"))

    @app.on_event("startup")
    async def _startup_metrics() -> None:
        from llm_cli.core import lifecycle_status, metrics
        from llm_cli.core.lifecycle import event_bus

        cur = lifecycle_status.current()
        if cur.get("running") and cur.get("runtime_id"):
            await metrics.scheduler().on_instance_started(
                config_id=str(cur["config_id"]),
                runtime_id=str(cur["runtime_id"]),
                host="127.0.0.1",
                port=int(cur.get("port", 8000)),
            )
        event_bus().subscribe_async(metrics.handle_lifecycle_event)

    @app.on_event("shutdown")
    async def _shutdown_metrics() -> None:
        from llm_cli.core import metrics

        await metrics.scheduler().stop_all()

    mount_spa(app, _dist_dir())
    return app
