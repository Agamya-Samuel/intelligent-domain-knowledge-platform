"""
Auth endpoints — expose the JWT bridge for testing and frontend integration.
"""

from fastapi import APIRouter, Depends

from app.core.security import CurrentUser
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me")
async def get_me(
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    """
    Return the currently authenticated user.
    Validates the Auth.js v5 JWT and returns user info.
    """
    return {
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name,
    }
