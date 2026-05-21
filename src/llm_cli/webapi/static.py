"""SPA static serving for dashboard/dist with index.html fallback."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException


class SPAStaticFiles(StaticFiles):
    """StaticFiles with index.html fallback for unknown paths."""

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or path in ("", "index.html"):
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404 and path not in ("", "index.html"):
            return await super().get_response("index.html", scope)
        return response


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
                        "message": "Dashboard frontend not built. Run `loco dashboard install`.",
                        "details": {"dist_dir": str(dist_dir)},
                        "fix_hint": "Run `loco dashboard install`",
                    }
                },
            )

        return

    app.mount("/", SPAStaticFiles(directory=str(dist_dir), html=True), name="spa")
