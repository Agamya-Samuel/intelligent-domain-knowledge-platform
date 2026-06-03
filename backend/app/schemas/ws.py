"""WebSocket Pydantic schemas — typed messages for real-time fine-tuning metrics."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class WSEventType(StrEnum):
    """WebSocket event types emitted during fine-tuning."""

    CONNECTED = "connected"
    STEP = "step"
    EPOCH = "epoch"
    EVAL = "eval"
    COMPLETE = "complete"
    ERROR = "error"
    PONG = "pong"


class WSStepData(BaseModel):
    """Data payload for a 'step' event."""

    step: int
    loss: float
    learning_rate: float | None = None
    epoch: float | None = None


class WSEpochData(BaseModel):
    """Data payload for an 'epoch' event."""

    epoch: int
    avg_loss: float
    eval_loss: float | None = None


class WSEvalData(BaseModel):
    """Data payload for an 'eval' event (post-training RAGAS metrics)."""

    faithfulness: float | None = None
    context_relevance: float | None = None
    answer_relevance: float | None = None
    context_recall: float | None = None


class WSCompleteData(BaseModel):
    """Data payload for a 'complete' event."""

    final_loss: float | None = None
    adapter_path: str | None = None
    cost: float | None = None
    duration_seconds: float | None = None
    total_steps: int | None = None


class WSErrorData(BaseModel):
    """Data payload for an 'error' event."""

    message: str
    stage: str = "unknown"


class WSMessage(BaseModel):
    """Generic WebSocket message envelope."""

    type: WSEventType
    job_id: str
    data: dict[str, Any] = Field(default_factory=dict)
