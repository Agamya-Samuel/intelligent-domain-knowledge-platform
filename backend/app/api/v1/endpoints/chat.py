"""
Chat endpoints — RAG chat with SSE streaming, session management.

All endpoints require authentication. Sessions are scoped to users.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.dependencies import get_current_user, get_db
from app.schemas.chat import (
    ChatRequest,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    CreateSessionRequest,
    SetModelVariantRequest,
)
from app.services.chat_service import (
    create_session,
    delete_session,
    get_session,
    list_sessions,
    set_model_variant,
    stream_chat,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# ── SSE Chat Endpoint ───────────────────────────────────────────────


@router.post(
    "",
    summary="Send a chat query (SSE streaming)",
    description=(
        "Send a query and receive a streaming response via Server-Sent Events. "
        "Events: token (text tokens), citation (source references), done (completion), error."
    ),
)
async def chat_query(
    body: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Process a RAG chat query and stream the response via SSE.

    Creates or resumes a session, retrieves relevant chunks, generates
    a streaming LLM response with citations.
    """
    async def event_generator():
        """Generate SSE events from the RAG pipeline."""
        try:
            async for event_type, event_data in stream_chat(
                db,
                user_id=user.user_id,
                query=body.query,
                session_id=body.session_id,
                model_variant=body.model_variant,
            ):
                yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
        except Exception as exc:
            logger.exception("SSE event generation failed")
            error_data = json.dumps({"error": "Internal error", "detail": str(exc)})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx proxy buffering off for SSE
        },
    )


# ── Session Management ─────────────────────────────────────────────


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
)
async def create_chat_session(
    body: CreateSessionRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Create a new empty chat session."""
    title = body.title if body else "New Chat"
    session = await create_session(db, user_id=user.user_id, title=title)
    return session


@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
    summary="List user's chat sessions",
)
async def list_chat_sessions(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatSessionResponse]:
    """List all chat sessions for the authenticated user."""
    sessions = await list_sessions(db, user.user_id, offset=offset, limit=limit)
    return sessions


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionDetailResponse,
    summary="Get session details with messages",
)
async def get_chat_session(
    session_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionDetailResponse:
    """Get a chat session with all its messages."""
    session = await get_session(db, session_id=session_id, user_id=user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session '{session_id}' not found",
        )
    return session


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session",
)
async def delete_chat_session(
    session_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a chat session and all its messages."""
    session = await get_session(db, session_id=session_id, user_id=user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session '{session_id}' not found",
        )
    await delete_session(db, session)
    logger.info("Chat session deleted: %s", session_id)


@router.post(
    "/sessions/{session_id}/model-variant",
    response_model=ChatSessionResponse,
    summary="Set active model variant for a session",
)
async def set_session_model_variant(
    session_id: str,
    body: SetModelVariantRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Switch between base and fine-tuned model for a session."""
    session = await get_session(db, session_id=session_id, user_id=user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session '{session_id}' not found",
        )
    updated = await set_model_variant(db, session, body.model_variant)
    return updated
