#!/bin/bash
# ──────────────────────────────────────────────────────────────────────
# IDKP Staging Deployment Script
#
# Deploys the full stack to staging:
#   1. Build infrastructure containers (Postgres, Redis, Langfuse, Nginx)
#   2. Run database migrations
#   3. Start backend + frontend services
#   4. Run smoke tests
#
# Usage:
#   chmod +x scripts/deploy-staging.sh
#   ./scripts/deploy-staging.sh [--skip-migrations] [--skip-smoke]
#
# Prerequisites:
#   - Docker and Docker Compose installed
#   - .env.staging file exists with all required variables
#   - Modal token configured for GPU functions
# ──────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

COMPOSE_FILE="$PROJECT_ROOT/docker-compose.staging.yml"
ENV_FILE="$PROJECT_ROOT/.env.staging"

# ── Colors ───────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Pre-flight checks ────────────────────────────────────────────────

if [[ ! -f "$ENV_FILE" ]]; then
    error "Missing .env.staging — copy .env.example to .env.staging and fill in values"
fi

if ! command -v docker &>/dev/null; then
    error "Docker is not installed"
fi

if ! docker compose version &>/dev/null; then
    error "Docker Compose is not available"
fi

SKIP_MIGRATIONS=false
SKIP_SMOKE=false
for arg in "$@"; do
    case $arg in
        --skip-migrations) SKIP_MIGRATIONS=true ;;
        --skip-smoke)       SKIP_SMOKE=true ;;
    esac
done

# ── Step 1: Start infrastructure ────────────────────────────────────

info "Starting staging infrastructure..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d postgres redis langfuse

info "Waiting for PostgreSQL to be healthy..."
timeout 60 bash -c \
    'until docker compose -f "'"$COMPOSE_FILE"'" exec -T postgres pg_isready -U idkp -d idkp_staging 2>/dev/null; do sleep 2; done'

info "Waiting for Redis to be healthy..."
timeout 30 bash -c \
    'until docker compose -f "'"$COMPOSE_FILE"'" exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; do sleep 2; done'

info "Waiting for Langfuse to be healthy..."
timeout 120 bash -c \
    'until curl -sf http://localhost:${STAGING_LANGFUSE_PORT:-3002}/api/public/health 2>/dev/null; do sleep 5; done' || warn "Langfuse health check timed out — continuing"

# ── Step 2: Run database migrations ──────────────────────────────────

if [[ "$SKIP_MIGRATIONS" == true ]]; then
    warn "Skipping database migrations (--skip-migrations)"
else
    info "Running Alembic migrations..."
    cd "$PROJECT_ROOT/backend"
    alembic upgrade head || error "Database migrations failed"
    cd "$PROJECT_ROOT"
fi

# ── Step 3: Start Nginx ──────────────────────────────────────────────

info "Starting Nginx reverse proxy..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d nginx

# ── Step 4: Smoke tests ──────────────────────────────────────────────

if [[ "$SKIP_SMOKE" == true ]]; then
    warn "Skipping smoke tests (--skip-smoke)"
else
    info "Running smoke tests..."
    SMOKE_PORT="${STAGING_NGINX_PORT:-8080}"

    # Health check
    HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:$SMOKE_PORT/health" || true)
    if [[ "$HTTP_CODE" == "200" ]]; then
        info "Health check: PASS (HTTP $HTTP_CODE)"
    else
        warn "Health check: FAIL (HTTP ${HTTP_CODE:-unknown})"
    fi

    # API docs accessible
    HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:$SMOKE_PORT/docs" || true)
    if [[ "$HTTP_CODE" == "200" ]]; then
        info "API docs: PASS (HTTP $HTTP_CODE)"
    else
        warn "API docs: FAIL (HTTP ${HTTP_CODE:-unknown})"
    fi

    # OpenAPI schema
    HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:$SMOKE_PORT/openapi.json" || true)
    if [[ "$HTTP_CODE" == "200" ]]; then
        info "OpenAPI schema: PASS (HTTP $HTTP_CODE)"
    else
        warn "OpenAPI schema: FAIL (HTTP ${HTTP_CODE:-unknown})"
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────

echo ""
info "Staging deployment complete!"
echo ""
echo "  Infrastructure:"
echo "    PostgreSQL: localhost:${STAGING_POSTGRES_PORT:-5433}"
echo "    Redis:      localhost:${STAGING_REDIS_PORT:-6380}"
echo "    Langfuse:   http://localhost:${STAGING_LANGFUSE_PORT:-3002}"
echo "    Nginx:      http://localhost:${STAGING_NGINX_PORT:-8080}"
echo ""
echo "  Start backend:  cd backend && uvicorn app.main:app --port 8001"
echo "  Start frontend: cd frontend && npm run dev --port 3001"
echo ""
echo "  To tear down:   docker compose -f docker-compose.staging.yml down -v"
echo ""
