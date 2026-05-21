"""In-process job coroutines for dashboard mutations (no CLI subprocess)."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from llm_cli.core import model_pull, runtime_install, update_ops


async def _run_sync(
    report: Callable[[dict[str, Any]], Awaitable[None]],
    *,
    stage: str,
    fn: Callable[[], Any],
) -> None:
    await report({"stage": stage})
    await asyncio.to_thread(fn)


async def runtime_install_job(
    runtime_id: str,
    report: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    params = runtime_install.default_build_param_tokens(runtime_id)

    def _run() -> None:
        try:
            runtime_install.install_runtime(
                runtime_id,
                param=params,
                yes=True,
            )
        except runtime_install.RuntimeInstallError as exc:
            raise RuntimeError(exc.message) from exc

    await _run_sync(report, stage="installing", fn=_run)


async def runtime_rebuild_job(
    runtime_id: str,
    *,
    reset: bool,
    report: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    def _run() -> None:
        try:
            runtime_install.rebuild_runtime(runtime_id, reset=reset, yes=True)
        except runtime_install.RuntimeInstallError as exc:
            raise RuntimeError(exc.message) from exc

    await _run_sync(report, stage="rebuilding", fn=_run)


async def model_pull_job(
    *,
    url: str,
    fmt: str | None,
    include: list[str],
    exclude: list[str],
    id_override: str | None,
    force: bool,
    report: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    def _run() -> None:
        try:
            model_pull.pull_hf_url_model_id(
                url,
                fmt=fmt,
                include=include or None,
                exclude=exclude or None,
                id_override=id_override,
                force=force,
            )
        except model_pull.PullModelError as exc:
            raise RuntimeError(str(exc)) from exc

    await _run_sync(report, stage="pulling", fn=_run)


async def update_job(
    *,
    restart: bool,
    report: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    def _run() -> None:
        try:
            update_ops.run_default_update(restart=restart)
        except update_ops.UpdateError as exc:
            raise RuntimeError(exc.message) from exc

    await _run_sync(report, stage="updating", fn=_run)
