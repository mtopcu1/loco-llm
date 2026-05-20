"""SPA static serving for dashboard/dist with index.html fallback."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


class SPAStaticFiles(StaticFiles):
    """StaticFiles with index.html fallback for unknown paths."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as e:
            if e.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


def mount_spa(app: FastAPI, dist_dir: Path) -> None:
    if not dist_dir.is_dir() or not (dist_dir / "index.html").is_file():

        @app.get("/{full_path:path}", include_in_schema=False)
        async def _not_installed(full_path: str, request: Request):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="not found")
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "DASHBOARD_NOT_BUILT",
                        "message": "Dashboard frontend not built. Run `llm dashboard install`.",
                        "details": {"dist_dir": str(dist_dir)},
                        "fix_hint": "Run `llm dashboard install`",
                    }
                },
            )

        return

    app.mount("/", SPAStaticFiles(directory=str(dist_dir), html=True), name="spa")
