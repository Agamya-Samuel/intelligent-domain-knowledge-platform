"""Central v1 API router — aggregates all v1 endpoints."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, documents, health

router = APIRouter()

router.include_router(health.router)
router.include_router(auth.router)
router.include_router(documents.router)
