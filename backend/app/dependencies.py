"""
FastAPI dependencies — auth extraction and database session injection.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, decode_authjs_token
from app.db.session import async_session_factory, get_db  # re-exported for endpoint use
from app.models.user import User

__all__ = ["get_current_user", "get_db", "get_db_context"]

logger = logging.getLogger(__name__)


async def _ensure_user_exists(
    db: AsyncSession, user: CurrentUser
) -> None:
    """
    Auto-upsert the authenticated user into the local users table.

    Auth.js is the identity provider — the local `users` table is a mirror.
    When a user authenticates for the first time, their record is created
    automatically to satisfy FK constraints (datasets, documents, etc.).
    """
    result = await db.execute(select(User).where(User.id == user.user_id))
    existing = result.scalar_one_or_none()

    if existing:
        # Update email/name if changed
        if existing.email != user.email:
            existing.email = user.email
        if existing.name != user.name:
            existing.name = user.name
    else:
        new_user = User(
            id=user.user_id,
            email=user.email,
            name=user.name,
        )
        db.add(new_user)
        logger.info("Auto-provisioned user: %s (%s)", user.user_id, user.email)

    try:
        await db.flush()
    except IntegrityError:
        # Race condition: concurrent request already created the user.
        # Rollback the failed insert and re-query.
        await db.rollback()
        result = await db.execute(select(User).where(User.id == user.user_id))
        existing = result.scalar_one_or_none()
        if existing:
            if existing.email != user.email:
                existing.email = user.email
            if existing.name != user.name:
                existing.name = user.name
            await db.flush()


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """
    Extract and validate the Auth.js v5 JWT from the request.

    Supports two token locations:
      1. Authorization header: "Bearer <token>"
      2. Cookie: "authjs.session-token" (Auth.js v5) or "next-auth.session-token" (v4)

    Also ensures the user exists in the local `users` table (auto-provisioning).
    """
    token: str | None = None

    # 1. Try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # 2. Fall back to Auth.js session cookie
    if token is None:
        token = request.cookies.get("authjs.session-token") or request.cookies.get("next-auth.session-token")

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

    # Auto-provision user in local DB (satisfies FK constraints)
    await _ensure_user_exists(db, user)

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
