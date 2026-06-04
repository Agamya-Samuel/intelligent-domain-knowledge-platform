"""
IDKP Backend — FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload --port 8000
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.config import settings
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup/shutdown lifecycle hook."""
    # Startup: configure observability
    _setup_observability()
    yield
    # Shutdown: cleanup resources


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

# ── API Routes ──────────────────────────────────────────────────────────────
app.include_router(v1_router)
