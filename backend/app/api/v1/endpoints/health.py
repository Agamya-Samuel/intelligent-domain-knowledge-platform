"""Health check endpoint — used by Docker health checks and monitoring."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return 200 if the backend is running."""
    return {"status": "ok"}
