"""Pydantic schemas — import all schemas here."""

from app.schemas.budget import BudgetEntryResponse, BudgetSummaryResponse
from app.schemas.chat import (
    ChatMessageResponse,
    ChatRequest,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    CreateSessionRequest,
    ModelVariant,
    SetModelVariantRequest,
    SSECitationEvent,
    SSEDoneEvent,
    SSEErrorEvent,
    SSETokenEvent,
)
from app.schemas.dataset import (
    DatasetCreateRequest,
    DatasetDetailResponse,
    DatasetResponse,
    DatasetSourceCreateResponse,
    DatasetSourceResponse,
    DatasetVersionResponse,
)
from app.schemas.document import (
    DocumentCreateResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentProcessResponse,
    DocumentUpdateRequest,
)
from app.schemas.document_chunk import DocumentChunkResponse
from app.schemas.evaluation import (
    EvalRunType,
    EvaluationCreateRequest,
    EvaluationHistoryResponse,
    EvaluationMetricsResponse,
    EvaluationRunResponse,
)
from app.schemas.fine_tuning import (
    FineTuneCreateRequest,
    FineTuneCreateResponse,
    FineTuneHistoryResponse,
    FineTuneStatusResponse,
)
from app.schemas.knowledge_entity import (
    KnowledgeEntityCreateRequest,
    KnowledgeEntityResponse,
)
from app.schemas.knowledge_relation import (
    KnowledgeRelationCreateRequest,
    KnowledgeRelationResponse,
)
from app.schemas.model_catalog import (
    ModelCatalogResponse,
    ModelDetailResponse,
    ModelInfo,
)
from app.schemas.user import UserCreateRequest, UserResponse

__all__ = [
    # Budget
    "BudgetEntryResponse",
    "BudgetSummaryResponse",
    # Chat
    "ChatMessageResponse",
    "ChatRequest",
    "ChatSessionDetailResponse",
    "ChatSessionResponse",
    "CreateSessionRequest",
    "ModelVariant",
    "SetModelVariantRequest",
    "SSEDoneEvent",
    "SSECitationEvent",
    "SSEErrorEvent",
    "SSETokenEvent",
    # Dataset
    "DatasetCreateRequest",
    "DatasetDetailResponse",
    "DatasetResponse",
    "DatasetSourceCreateResponse",
    "DatasetSourceResponse",
    "DatasetVersionResponse",
    # Document
    "DocumentChunkResponse",
    "DocumentCreateResponse",
    "DocumentDetailResponse",
    "DocumentListResponse",
    "DocumentProcessResponse",
    "DocumentUpdateRequest",
    # Evaluation
    "EvaluationCreateRequest",
    "EvaluationHistoryResponse",
    "EvaluationMetricsResponse",
    "EvaluationRunResponse",
    "EvalRunType",
    # Fine-tuning
    "FineTuneCreateRequest",
    "FineTuneCreateResponse",
    "FineTuneHistoryResponse",
    "FineTuneStatusResponse",
    # Knowledge
    "KnowledgeEntityCreateRequest",
    "KnowledgeEntityResponse",
    "KnowledgeRelationCreateRequest",
    "KnowledgeRelationResponse",
    # Model catalog
    "ModelCatalogResponse",
    "ModelDetailResponse",
    "ModelInfo",
    # User
    "UserCreateRequest",
    "UserResponse",
]
