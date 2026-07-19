"""
Security headers middleware — adds OWASP-recommended headers to every response.

This is a defence-in-depth measure: the frontend (Vercel) sets its own headers,
and nginx can also set them, but adding them in the backend means *every*
endpoint — even those proxied directly — is protected.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject security headers into every HTTP response."""

    def __init__(self, app, *, is_production: bool = True) -> None:
        super().__init__(app)
        self.is_production = is_production

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Always
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("X-DNS-Prefetch-Control", "off")

        # HSTS only in production over HTTPS
        if self.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )

        # Remove identifying headers
        if "server" in response.headers:
            del response.headers["server"]

        return response
