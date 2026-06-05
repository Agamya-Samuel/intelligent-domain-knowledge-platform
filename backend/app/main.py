"""
IDKP Backend — FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload --port 8000
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.config import settings
from app.middleware.csrf import CSRFDetectionMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)


def _setup_observability() -> None:
    """Configure OpenTelemetry + Langfuse tracing (lazy — no-op if not configured)."""
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Only initialize if Langfuse is configured
        if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
            logger.info("Langfuse not configured — skipping OpenTelemetry setup")
            return

        resource = Resource.create({"service.name": "idkp-backend"})
        tracer_provider = TracerProvider(resource=resource)

        # Langfuse accepts OTLP gRPC traces
        otlp_exporter = OTLPSpanExporter(
            endpoint=f"{settings.LANGFUSE_HOST}/api/public/otlp",
            headers={
                "x-langfuse-public-key": settings.LANGFUSE_PUBLIC_KEY,
                "x-langfuse-secret-key": settings.LANGFUSE_SECRET_KEY,
            },
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(tracer_provider)

        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)

        logger.info("OpenTelemetry + Langfuse tracing initialized")
    except ImportError:
        logger.info("OpenTelemetry packages not installed — skipping tracing")


# ── Queue background worker ────────────────────────────────────────────────

_QUEUE_POLL_INTERVAL = 30  # seconds between queue checks
_MODAL_POLL_INTERVAL = 15  # seconds between Modal completion checks
_queue_worker_task: asyncio.Task | None = None
_modal_poller_task: asyncio.Task | None = None


async def _queue_worker() -> None:
    """
    Background task that periodically polls the training queue.

    Every ``_QUEUE_POLL_INTERVAL`` seconds, checks if there is a queued
    fine-tuning job with no active job running.  If so, submits it.
    This ensures jobs are picked up even if the original background task
    from the API endpoint failed silently.
    """
    from app.dependencies import get_db_context
    from app.services.training_service import process_queue, submit_training_job

    logger.info("Queue worker started (poll interval=%ds)", _QUEUE_POLL_INTERVAL)
    while True:
        try:
            await asyncio.sleep(_QUEUE_POLL_INTERVAL)
            async with get_db_context() as db:
                job = await process_queue(db)
                if job:
                    logger.info("Queue worker: submitting job %s", job.id)
                    await submit_training_job(db, job.id)
        except asyncio.CancelledError:
            logger.info("Queue worker cancelled — shutting down")
            break
        except Exception:
            logger.exception("Queue worker error")


async def _modal_job_poller() -> None:
    """
    Background task that polls Modal for training job completion.

    Every ``_MODAL_POLL_INTERVAL`` seconds, checks all jobs in
    ``training``/``evaluating`` status to see if their Modal function
    has returned.  Completed jobs are finalized; failed jobs are marked.
    """
    from app.dependencies import get_db_context
    from app.services.training_service import poll_modal_jobs

    logger.info("Modal job poller started (poll interval=%ds)", _MODAL_POLL_INTERVAL)
    while True:
        try:
            await asyncio.sleep(_MODAL_POLL_INTERVAL)
            async with get_db_context() as db:
                completed = await poll_modal_jobs(db)
                if completed:
                    logger.info("Modal poller: resolved jobs %s", completed)
        except asyncio.CancelledError:
            logger.info("Modal job poller cancelled — shutting down")
            break
        except Exception:
            logger.exception("Modal job poller error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup/shutdown lifecycle hook."""
    global _queue_worker_task, _modal_poller_task

    _setup_observability()

    _queue_worker_task = asyncio.create_task(_queue_worker())
    _modal_poller_task = asyncio.create_task(_modal_job_poller())
    logger.info("Started training queue worker + Modal job poller")

    yield

    if _queue_worker_task:
        _queue_worker_task.cancel()
        try:
            await _queue_worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Queue worker stopped")

    if _modal_poller_task:
        _modal_poller_task.cancel()
        try:
            await _modal_poller_task
        except asyncio.CancelledError:
            pass
        logger.info("Modal job poller stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Intelligent Domain Knowledge Platform — REST API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting ──────────────────────────────────────────────────────────
app.add_middleware(RateLimitMiddleware)

# ── CSRF Protection ───────────────────────────────────────────────────────
app.add_middleware(CSRFDetectionMiddleware)

# ── API Routes ──────────────────────────────────────────────────────────────
app.include_router(v1_router)
