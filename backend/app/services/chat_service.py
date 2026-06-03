"""
Chat service — orchestrates the full RAG chat pipeline.

Flow:
    1. Create/resume a chat session
    2. Store user message
    3. Retrieve relevant chunks via RAG retriever
    4. Build RAG prompt from retrieved context
    5. Stream LLM generation as SSE events
    6. Store assistant message with citations
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import generate_uuid
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.services.rag.llm_client import generate_stream
from app.services.rag.prompt_builder import build_rag_prompt, extract_citations
from app.services.rag.retriever import retrieve

logger = logging.getLogger(__name__)


# ── Session CRUD ────────────────────────────────────────────────────


async def create_session(
    db: AsyncSession,
    *,
    user_id: str,
    title: str = "New Chat",
    model_variant: str = "base",
) -> ChatSession:
    """Create a new chat session."""
    session = ChatSession(
        id=generate_uuid(),
        user_id=user_id,
        title=title,
        model_variant=model_variant,
    )
    db.add(session)
    await db.flush()
    return session


async def get_session(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> ChatSession | None:
    """Fetch a chat session scoped to a specific user."""
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession,
    user_id: str,
    *,
    offset: int = 0,
    limit: int = 20,
) -> list[ChatSession]:
    """List chat sessions for a user with pagination."""
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_session_title(
    db: AsyncSession,
    session: ChatSession,
    title: str,
) -> ChatSession:
    """Update the title of a chat session."""
    session.title = title
    await db.flush()
    return session


async def set_model_variant(
    db: AsyncSession,
    session: ChatSession,
    model_variant: str,
) -> ChatSession:
    """Set the active model variant for a session."""
    session.model_variant = model_variant
    await db.flush()
    return session


async def delete_session(
    db: AsyncSession,
    session: ChatSession,
) -> None:
    """Delete a chat session and all its messages."""
    await db.delete(session)
    await db.flush()


# ── Message Persistence ─────────────────────────────────────────────


async def store_message(
    db: AsyncSession,
    *,
    session_id: str,
    role: str,
    content: str,
    citations: list[dict] | None = None,
    latency_ms: int | None = None,
    token_count: int | None = None,
) -> ChatMessage:
    """Store a message in the database."""
    message = ChatMessage(
        id=generate_uuid(),
        session_id=session_id,
        role=role,
        content=content,
        citations=citations,
        latency_ms=latency_ms,
        token_count=token_count,
    )
    db.add(message)
    await db.flush()
    return message


# ── RAG Chat Pipeline ───────────────────────────────────────────────


async def stream_chat(
    db: AsyncSession,
    *,
    user_id: str,
    query: str,
    session_id: str | None = None,
    model_variant: str = "base",
    doc_type: str | None = None,
    source_id: str | None = None,
    page: int | None = None,
    section: str | None = None,
) -> AsyncGenerator[tuple[str, dict[str, Any]], None]:
    """
    Execute the full RAG chat pipeline and stream tokens via SSE events.

    Yields:
        Tuples of (event_type, event_data) where:
          - event_type: "token", "citation", "done", or "error"
          - event_data: Dict compatible with the SSE schema classes

    The caller (endpoint) converts these to SSE format.
    """
    start_time = time.monotonic()
    effective_session_id = session_id
    message_id = generate_uuid()

    try:
        # Step 1: Get or create session
        session: ChatSession | None = None
        if session_id:
            session = await get_session(db, session_id=session_id, user_id=user_id)

        if session is None:
            session = await create_session(
                db,
                user_id=user_id,
                title=query[:100],
                model_variant=model_variant,
            )
            effective_session_id = session.id
            logger.info("Created new chat session %s for user %s", session.id, user_id)

        # Step 2: Store user message
        await store_message(
            db,
            session_id=effective_session_id,
            role="user",
            content=query,
        )
        await db.flush()

        # Step 3: Retrieve relevant chunks (with advanced RAG pipeline)
        retrieval = await retrieve(
            query,
            doc_type=doc_type,
            source_id=source_id,
            page=page,
            section=section,
        )

        # Step 4: Send citation events
        citations = extract_citations(retrieval)
        for citation in citations:
            yield ("citation", citation)

        # Step 5: Build RAG prompt
        prompt = build_rag_prompt(retrieval)

        # Step 6: Stream LLM response
        full_response = ""
        async for token in generate_stream(prompt, system_prompt=None):
            full_response += token
            yield ("token", {"content": token, "citations": None})

        # Step 7: Calculate latency and store assistant message
        latency_ms = int((time.monotonic() - start_time) * 1000)
        token_count = len(full_response) // 4  # approximate

        await store_message(
            db,
            session_id=effective_session_id,
            role="assistant",
            content=full_response,
            citations=citations if citations else None,
            latency_ms=latency_ms,
            token_count=token_count,
        )
        await db.flush()

        # Step 8: Send done event
        yield (
            "done",
            {
                "latency_ms": latency_ms,
                "model_variant": model_variant,
                "citations_count": len(citations),
                "message_id": message_id,
                "session_id": effective_session_id,
            },
        )

    except Exception as exc:
        logger.exception("RAG chat pipeline failed")
        yield (
            "error",
            {
                "error": "Chat generation failed",
                "detail": str(exc),
            },
        )
