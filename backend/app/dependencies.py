"""
FastAPI dependencies — auth extraction and database session injection.
"""

from fastapi import Depends, HTTPException, Request, status

from app.core.security import CurrentUser, decode_authjs_token
from app.db.session import get_db  # re-exported for endpoint use

__all__ = ["get_current_user", "get_db"]


async def get_current_user(request: Request) -> CurrentUser:
    """
    Extract and validate the Auth.js v5 JWT from the request.

    Supports two token locations:
      1. Authorization header: "Bearer <token>"
      2. Cookie: "next-auth.session-token" (Auth.js v5 default cookie name)
    """
    token: str | None = None

    # 1. Try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # 2. Fall back to Auth.js session cookie
    if token is None:
        token = request.cookies.get("next-auth.session-token")

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — no token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = decode_authjs_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return user
