"""Uniform error response shape for the webapi."""
from __future__ import annotations

import logging
import uuid
from enum import Enum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("llm_cli.webapi.errors")


class ErrorCode(str, Enum):
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"

    DASHBOARD_NOT_INSTALLED = "DASHBOARD_NOT_INSTALLED"
    DASHBOARD_VERSION_MISMATCH = "DASHBOARD_VERSION_MISMATCH"

    RUNTIME_NOT_FOUND = "RUNTIME_NOT_FOUND"
    RUNTIME_NOT_INSTALLED = "RUNTIME_NOT_INSTALLED"
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"

    INSTANCE_NOT_RUNNING = "INSTANCE_NOT_RUNNING"
    INSTANCE_ALREADY_RUNNING = "INSTANCE_ALREADY_RUNNING"

    SETTINGS_UNKNOWN_KEY = "SETTINGS_UNKNOWN_KEY"

    # Mutation-specific
    RUNTIME_ALREADY_INSTALLED = "RUNTIME_ALREADY_INSTALLED"
    RUNTIME_IN_USE = "RUNTIME_IN_USE"
    MODEL_ALREADY_REGISTERED = "MODEL_ALREADY_REGISTERED"
    MODEL_PULL_INVALID_URL = "MODEL_PULL_INVALID_URL"
    CONFIG_ALREADY_EXISTS = "CONFIG_ALREADY_EXISTS"
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_IN_USE = "CONFIG_IN_USE"
    INSTANCE_FOREGROUND_NOT_SWITCHABLE = "INSTANCE_FOREGROUND_NOT_SWITCHABLE"
    INSTANCE_FOREGROUND_NOT_STOPPABLE = "INSTANCE_FOREGROUND_NOT_STOPPABLE"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_NOT_CANCELABLE = "JOB_NOT_CANCELABLE"
    SETTINGS_VALIDATION_FAILED = "SETTINGS_VALIDATION_FAILED"


class ApiError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        fix_hint: str | None = None,
        status_code: int = 400,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        self.fix_hint = fix_hint
        self.status_code = status_code
        super().__init__(message)


def _error_body(
    code: str, message: str, details: dict[str, Any], fix_hint: str | None, request: Request
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "fix_hint": fix_hint,
        },
        "request_id": getattr(request.state, "request_id", str(uuid.uuid4())),
    }


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code.value, exc.message, exc.details, exc.fix_hint, request),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled exception", extra={"request_id": getattr(request.state, "request_id", "?")}
        )
        return JSONResponse(
            status_code=500,
            content=_error_body(
                ErrorCode.INTERNAL_ERROR.value,
                "An unexpected error occurred. Check server logs for details.",
                {},
                None,
                request,
            ),
        )
