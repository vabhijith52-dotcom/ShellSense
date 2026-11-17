"""API security middleware and token verification.

Section 10: Per-launch 32-byte session token, constant-time validation,
Host and Origin allowlist (preventing DNS rebinding and CSRF), and strict CSP headers.
"""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class SessionSecurity:
    """Generates and verifies in-memory single-launch session token."""

    def __init__(self, token: str | None = None, port: int = 5173) -> None:
        self.token = token or secrets.token_hex(32)
        self.port = port
        self.allowed_hosts = {
            f"127.0.0.1:{self.port}",
            f"localhost:{self.port}",
            "127.0.0.1",
            "localhost",
        }

    def verify_token(self, provided_token: str | None) -> bool:
        if not provided_token:
            return False
        # Remove 'Bearer ' prefix if present
        clean_token = provided_token.removeprefix("Bearer ").strip()
        return hmac.compare_digest(self.token, clean_token)

    def verify_host(self, host_header: str | None) -> bool:
        if not host_header:
            return False
        return host_header in self.allowed_hosts


class SecurityMiddleware(BaseHTTPMiddleware):
    """Enforces Host/Origin checks, token validation, and strict headers."""

    def __init__(self, app: Any, security: SessionSecurity) -> None:
        super().__init__(app)
        self.security = security

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        # 1. Host header validation (defeats DNS rebinding)
        host = request.headers.get("host")
        if not self.security.verify_host(host):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Forbidden: Host header mismatch."},
            )

        # 2. Origin validation for state-changing HTTP methods
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin:
                # Strip protocol to check host:port
                clean_origin = origin.replace("http://", "").replace("https://", "")
                if not self.security.verify_host(clean_origin):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Forbidden: Origin header mismatch."},
                    )

        # 3. Session token authorization check (exempt static /docs if enabled)
        if request.url.path.startswith("/api/v1"):
            auth_header = request.headers.get("authorization")
            if not self.security.verify_token(auth_header):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Unauthorized: Invalid or missing session token."},
                )

        response: Response = await call_next(request)

        # 4. Strict Security Headers (Section 10)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self' ws://127.0.0.1:* http://127.0.0.1:*; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self';"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["X-Frame-Options"] = "DENY"

        return response
