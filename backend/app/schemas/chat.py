"""Chat Pydantic schemas — request/response models for the chat RAG pipeline."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(StrEnum):
    """Chat message roles."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ModelVariant(StrEnum):
    """LLM model variant selection."""

    BASE = "base"
    FINETUNED = "finetuned"


# ── Request Schemas ─────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    query: str = Field(..., min_length=1, max_length=2000, description="User question or query")
    session_id: str | None = Field(
        default=None,
        description="Existing session ID. If None, a new session is created.",
    )
    model_variant: ModelVariant = Field(
        default=ModelVariant.BASE,
        description="Which LLM variant to use for generation.",
    )


class CreateSessionRequest(BaseModel):
    """Request body for creating a new chat session."""

    title: str = Field(default="New Chat", max_length=500, description="Session title")


class SetModelVariantRequest(BaseModel):
    """Request body for switching the active model variant."""

    model_variant: ModelVariant = Field(
        ...,
        description="The model variant to activate for this session.",
    )


# ── Response Schemas ────────────────────────────────────────────────


class ChatMessageResponse(BaseModel):
    """A chat message returned in session history."""

    id: str
    session_id: str
    role: MessageRole
    content: str
    citations: list[dict] | None = None
    latency_ms: int | None = None
    token_count: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionResponse(BaseModel):
    """Summary of a chat session (list view)."""

    id: str
    user_id: str
    title: str
    model_variant: ModelVariant
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionDetailResponse(BaseModel):
    """Chat session with its messages."""

    id: str
    user_id: str
    title: str
    model_variant: ModelVariant
    messages: list[ChatMessageResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── SSE Event Schemas (TRD §6.6) ───────────────────────────────────


class SSETokenEvent(BaseModel):
    """event: token — a streaming text token."""

    content: str
    citations: list[dict] | None = None


class SSECitationEvent(BaseModel):
    """event: citation — a source citation from retrieval."""

    source: str
    page: int | None = None
    section: str | None = None


class SSEDoneEvent(BaseModel):
    """event: done — signals the end of the stream."""

    latency_ms: int
    model_variant: str
    citations_count: int
    message_id: str
    session_id: str


class SSEErrorEvent(BaseModel):
    """event: error — signals an error during streaming."""

    error: str
    detail: str | None = None
