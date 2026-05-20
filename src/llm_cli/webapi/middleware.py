"""Webapi middleware: Host header allow-list, security headers, request-id."""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self'"
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class HostHeaderMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allowed_hosts: set[str]) -> None:
        super().__init__(app)
        self.allowed_hosts = {h.lower() for h in allowed_hosts}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        host = (request.headers.get("host") or "").lower()
        if host not in self.allowed_hosts:
            return JSONResponse(
                status_code=421,
                content={
                    "error": {
                        "code": "BAD_HOST_HEADER",
                        "message": f"Host header '{host}' is not allowed.",
                        "details": {"allowed": sorted(self.allowed_hosts)},
                        "fix_hint": None,
                    },
                    "request_id": getattr(request.state, "request_id", uuid.uuid4().hex),
                },
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, insecure: bool = False) -> None:
        super().__init__(app)
        self.insecure = insecure

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "()"
        response.headers["Content-Security-Policy"] = CSP
        if self.insecure:
            response.headers["X-LocalLLM-Insecure"] = "true"
        return response
