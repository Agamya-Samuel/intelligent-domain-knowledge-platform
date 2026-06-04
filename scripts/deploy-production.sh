#!/bin/bash
# ──────────────────────────────────────────────────────────────────────
# IDKP Production Deployment Script
#
# Deploys the full stack to production:
#   1. Pre-flight checks (Docker, .env.production, SSL certs, ports)
#   2. Start infrastructure containers (Postgres, Redis, Langfuse, Nginx)
#   3. Wait for healthy services
#   4. Run database migrations
#   5. Run production smoke tests
#
# Usage:
#   chmod +x scripts/deploy-production.sh
#   ./scripts/deploy-production.sh [--skip-migrations] [--skip-smoke] [--rollback]
#
# Prerequisites:
#   - Docker and Docker Compose installed
#   - .env.production file with all secrets
#   - SSL certificates at ./certs/fullchain.pem and ./certs/privkey.pem
#   - Backend and Frontend running on host (ports 8000/3000)
# ──────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

COMPOSE_FILE="$PROJECT_ROOT/docker-compose.prod.yml"
ENV_FILE="$PROJECT_ROOT/.env.production"
CERTS_DIR="$PROJECT_ROOT/certs"

# ── Colors ───────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
step()  { echo -e "${BLUE}[STEP]${NC}  $*"; }

# ── Parse arguments ─────────────────────────────────────────────────
SKIP_MIGRATIONS=false
SKIP_SMOKE=false
ROLLBACK=false
for arg in "$@"; do
    case $arg in
        --skip-migrations) SKIP_MIGRATIONS=true ;;
        --skip-smoke)       SKIP_SMOKE=true ;;
        --rollback)         ROLLBACK=true ;;
        *)                  warn "Unknown argument: $arg" ;;
    esac
done

# ── Rollback mode ────────────────────────────────────────────────────
if [[ "$ROLLBACK" == true ]]; then
    step "Rolling back production deployment..."
    info "Stopping all production containers..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down --timeout 120

    info "Production containers stopped."
    echo ""
    echo "  To re-deploy:  ./scripts/deploy-production.sh"
    echo "  To restart:    docker compose -f docker-compose.prod.yml --env-file .env.production up -d"
    exit 0
fi

# ── Pre-flight checks ────────────────────────────────────────────────
step "Running pre-flight checks..."

if [[ ! -f "$ENV_FILE" ]]; then
    error "Missing .env.production — copy .env.production.example to .env.production and fill in values"
fi

if [[ ! -f "$CERTS_DIR/fullchain.pem" ]] || [[ ! -f "$CERTS_DIR/privkey.pem" ]]; then
    error "Missing SSL certificates at ./certs/fullchain.pem and ./certs/privkey.pem"
fi

if ! command -v docker &>/dev/null; then
    error "Docker is not installed"
fi

if ! docker compose version &>/dev/null; then
    error "Docker Compose is not available"
fi

# Check required ports are free
for port in 80 443 5432; do
    if ss -tlnp 2>/dev/null | grep -q ":${port} " || netstat -tlnp 2>/dev/null | grep -q ":${port} "; then
        warn "Port $port is already in use — this may conflict with production services"
    fi
done

info "Pre-flight checks passed"

# ── Step 1: Start infrastructure ────────────────────────────────────
step "Starting production infrastructure..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d postgres redis langfuse

step "Waiting for PostgreSQL to be healthy..."
timeout 120 bash -c \
    'until docker compose -f "'"$COMPOSE_FILE"'" exec -T postgres pg_isready -U idkp -d idkp 2>/dev/null; do sleep 3; done'

step "Waiting for Redis to be healthy..."
timeout 60 bash -c \
    'until docker compose -f "'"$COMPOSE_FILE"'" exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; do sleep 3; done'

step "Waiting for Langfuse to be healthy..."
timeout 180 bash -c \
    'until curl -sf http://localhost:${PROD_LANGFUSE_PORT:-3001}/api/public/health 2>/dev/null; do sleep 5; done' || warn "Langfuse health check timed out — continuing (non-critical)"

info "Infrastructure services healthy"

# ── Step 2: Run database migrations ──────────────────────────────────
if [[ "$SKIP_MIGRATIONS" == true ]]; then
    warn "Skipping database migrations (--skip-migrations)"
else
    step "Running Alembic migrations..."
    cd "$PROJECT_ROOT/backend"
    alembic upgrade head || error "Database migrations failed — aborting deployment"
    cd "$PROJECT_ROOT"
    info "Migrations applied successfully"
fi

# ── Step 3: Start Nginx ──────────────────────────────────────────────
step "Starting Nginx reverse proxy..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d nginx
info "Nginx started with SSL termination"

# ── Step 4: Production smoke tests ────────────────────────────────────
if [[ "$SKIP_SMOKE" == true ]]; then
    warn "Skipping smoke tests (--skip-smoke)"
else
    step "Running production smoke tests..."
    PASS=0
    FAIL=0
    DOMAIN="${PROD_DOMAIN:-idkp.example.com}"
    BASE_URL="https://$DOMAIN"

    # Health check
    if curl -sf --max-time 10 "$BASE_URL/health" -o /dev/null; then
        info "  [PASS] Health endpoint"
        ((PASS++))
    else
        warn "  [FAIL] Health endpoint"
        ((FAIL++))
    fi

    # API docs
    if curl -sf --max-time 10 "$BASE_URL/docs" -o /dev/null; then
        info "  [PASS] API documentation"
        ((PASS++))
    else
        warn "  [FAIL] API documentation"
        ((FAIL++))
    fi

    # OpenAPI schema
    if curl -sf --max-time 10 "$BASE_URL/openapi.json" -o /dev/null; then
        info "  [PASS] OpenAPI schema"
        ((PASS++))
    else
        warn "  [FAIL] OpenAPI schema"
        ((FAIL++))
    fi

    # SSL verification
    if curl -sf --max-time 10 "https://$DOMAIN" -o /dev/null; then
        info "  [PASS] SSL certificate"
        ((PASS++))
    else
        warn "  [FAIL] SSL certificate"
        ((FAIL++))
    fi

    # WebSocket endpoint
    if curl -sf --max-time 5 --include "https://$DOMAIN/ws/finetune/jobs" 2>/dev/null | head -1 | grep -q "401\|403\|426"; then
        info "  [PASS] WebSocket endpoint responds"
        ((PASS++))
    else
        warn "  [FAIL] WebSocket endpoint"
        ((FAIL++))
    fi

    echo ""
    info "Smoke tests: $PASS passed, $FAIL failed"

    if [[ "$FAIL" -gt 0 ]]; then
        warn "Some smoke tests failed — review before going live"
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────
echo ""
info "Production deployment complete!"
echo ""
echo "  Infrastructure:"
echo "    PostgreSQL:  localhost:${PROD_POSTGRES_PORT:-5432}"
echo "    Redis:      localhost:${PROD_REDIS_PORT:-6379}"
echo "    Langfuse:   https://${PROD_LANGFUSE_URL:-langfuse.idkp.example.com}"
echo "    Nginx:      https://${PROD_DOMAIN:-idkp.example.com}"
echo ""
echo "  Start backend:  cd backend && uvicorn app.main:app --port 8000 --workers 4"
echo "  Start frontend: cd frontend && npm run build && npm run start"
echo ""
echo "  Useful commands:"
echo "    View logs:     docker compose -f docker-compose.prod.yml logs -f"
echo "    Stop all:      docker compose -f docker-compose.prod.yml down"
echo "    Rollback:      ./scripts/deploy-production.sh --rollback"
echo "    Smoke test:    ./scripts/smoke-test.sh"
echo ""
