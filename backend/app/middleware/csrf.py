"""CSRF protection middleware — validates CSRF token for state-changing requests."""

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class CSRFDetectionMiddleware(BaseHTTPMiddleware):
    """
    Require X-CSRF-Token header for all non-GET methods.

    JWT-based auth provides some protection, but this adds defense-in-depth
    for cookie-based authentication flows.
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    async def dispatch(self, request: Request, call_next) -> Response:
        # Allow safe methods without CSRF check
        if request.method in self.SAFE_METHODS:
            return await call_next(request)

        # Only enforce on API routes
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Skip for auth routes (managed by NextAuth.js CSRF)
        if request.url.path.startswith("/api/auth"):
            return await call_next(request)

        # Check for CSRF token in header
        csrf_token = request.headers.get("X-CSRF-Token") or request.headers.get("X-Requested-With")
        if not csrf_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing — include X-CSRF-Token header",
            )

        return await call_next(request)
