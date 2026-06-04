"""
FastAPI dependencies — auth extraction and database session injection.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, decode_authjs_token
from app.db.session import async_session_factory, get_db  # re-exported for endpoint use

__all__ = ["get_current_user", "get_db", "get_db_context"]

logger = logging.getLogger(__name__)


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
        logger.warning("Invalid token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return user


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that yields a database session.

    Use in non-FastAPI contexts (e.g., WebSocket handlers) where the
    standard FastAPI dependency injection is not available.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
