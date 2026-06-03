"""Model Catalog Pydantic schemas — static catalog read from MODEL_CATALOG config."""

from pydantic import BaseModel, ConfigDict


class ModelInfo(BaseModel):
    """Single model entry from the MODEL_CATALOG."""

    id: str
    name: str
    tier: int
    size: str
    gpu: str
    vram_gb: float
    est_cost: float
    est_time_min: int
    license: str
    available: bool = True
    quality_rating: float | None = None


class ModelCatalogResponse(BaseModel):
    """GET /api/models — all models across all tiers."""

    models: list[ModelInfo]


class ModelDetailResponse(BaseModel):
    """GET /api/models/{id} — single model detail."""

    id: str
    name: str
    tier: int
    size: str
    gpu: str
    vram_gb: float
    est_cost: float
    est_time_min: int
    license: str
    available: bool = True
    quality_rating: float | None = None

    model_config = ConfigDict(from_attributes=True)
