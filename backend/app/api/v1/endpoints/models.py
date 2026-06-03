"""Model Catalog endpoints — static catalog read from MODEL_CATALOG config."""

from fastapi import APIRouter, Depends, HTTPException

from app.config import MODEL_CATALOG
from app.core.security import CurrentUser
from app.dependencies import get_current_user
from app.schemas.model_catalog import ModelCatalogResponse, ModelDetailResponse

router = APIRouter(prefix="/api/v1/models", tags=["models"])


def _find_model(model_id: str) -> dict | None:
    """Look up a model by ID in the static catalog."""
    for m in MODEL_CATALOG:
        if m["id"] == model_id:
            return m
    return None


@router.get("", response_model=ModelCatalogResponse, summary="List all models")
async def list_models(
    _user: CurrentUser = Depends(get_current_user),
) -> ModelCatalogResponse:
    """Return all models across all tiers from the static MODEL_CATALOG."""
    return ModelCatalogResponse(models=MODEL_CATALOG)


@router.get(
    "/{model_id}",
    response_model=ModelDetailResponse,
    summary="Get model details",
)
async def get_model(
    model_id: str,
    _user: CurrentUser = Depends(get_current_user),
) -> ModelDetailResponse:
    """Return details for a single model by ID."""
    model = _find_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return ModelDetailResponse(**model)
