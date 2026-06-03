"""Central v1 API router — aggregates all v1 endpoints."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    budget,
    chat,
    documents,
    evaluation,
    fine_tune,
    health,
    models,
    ws,
)

router = APIRouter()

router.include_router(health.router)
router.include_router(auth.router)
router.include_router(documents.router)
router.include_router(chat.router)
router.include_router(models.router)
router.include_router(budget.router)
router.include_router(fine_tune.router)
router.include_router(evaluation.router)
router.include_router(ws.router)
