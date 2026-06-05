#!/bin/bash
# ──────────────────────────────────────────────────────────────────────
# IDKP Runbook: Modal Deployment
#
# Deploys or updates Modal production functions (inference, embeddings,
# reranker). Supports deploying individual functions or all at once.
#
# Usage:
#   chmod +x scripts/runbooks/modal-deploy.sh
#   ./scripts/runbooks/modal-deploy.sh              # Deploy all functions
#   ./scripts/runbooks/modal-deploy.sh --inference   # Deploy inference only
#   ./scripts/runbooks/modal-deploy.sh --embeddings  # Deploy embeddings only
#   ./scripts/runbooks/modal-deploy.sh --reranker    # Deploy reranker only
#   ./scripts/runbooks/modal-deploy.sh --status      # Check deployment status
#
# Prerequisites:
#   - Modal CLI installed and authenticated
#   - modal-production.py in scripts/ directory
#   - Modal secret "idkp-secrets" configured with required keys
#
# Cost impact:
#   - Functions are scale-to-zero (no cost when idle)
#   - Cold start: ~30-60s for GPU functions
#   - Running costs billed per second of GPU usage
# ──────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── Colors ───────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $*"; }
warn()  { echo -e "${YELLOW}[$(date '+%H:%M:%S')]${NC} $*"; }
error() { echo -e "${RED}[$(date '+%H:%M:%S')]${NC} $*"; exit 1; }
step()  { echo -e "${BLUE}[STEP]${NC}  $*"; }

# ── Parse arguments ─────────────────────────────────────────────────
DEPLOY_ALL=true
DEPLOY_INFERENCE=false
DEPLOY_EMBEDDINGS=false
DEPLOY_RERANKER=false
DEPLOY_TRAINING=false
SHOW_STATUS=false

for arg in "$@"; do
    case $arg in
        --all)         DEPLOY_ALL=true ;;
        --inference)   DEPLOY_ALL=false; DEPLOY_INFERENCE=true ;;
        --embeddings)  DEPLOY_ALL=false; DEPLOY_EMBEDDINGS=true ;;
        --reranker)    DEPLOY_ALL=false; DEPLOY_RERANKER=true ;;
        --training)    DEPLOY_ALL=false; DEPLOY_TRAINING=true ;;
        --status)      SHOW_STATUS=true; DEPLOY_ALL=false ;;
    esac
done

# ── Pre-flight checks ──────────────────────────────────────────────
if [[ "$SHOW_STATUS" == true ]]; then
    step "Checking Modal deployment status..."
    if ! command -v modal &>/dev/null; then
        error "Modal CLI not installed — install with: pip install modal"
    fi

    info "  App: idkp-production"
    info "  App: idkp-train (QLoRA training)"
    echo ""

    # List all functions in the app
    modal app list 2>/dev/null || warn "Could not list Modal apps"

    echo ""
    info "To check individual function status:"
    info "  modal app logs idkp-production.inference"
    info "  modal app logs idkp-production.embeddings"
    info "  modal app logs idkp-production.reranker"
    echo ""
    info "To check costs:"
    info "  modal cost"
    exit 0
fi

step "Pre-flight checks..."

if ! command -v modal &>/dev/null; then
    error "Modal CLI not installed — install with: pip install modal"
fi

MODAL_SCRIPT="$PROJECT_ROOT/scripts/modal-production.py"
if [[ ! -f "$MODAL_SCRIPT" ]]; then
    error "Modal production script not found at $MODAL_SCRIPT"
fi

# ── Deploy inference (vLLM on A10G) ──────────────────────────────────
if [[ "$DEPLOY_ALL" == true ]] || [[ "$DEPLOY_INFERENCE" == true ]]; then
    step "Deploying inference function (vLLM on A10G)..."

    # Deploy just the inference function
    cd "$PROJECT_ROOT"
    modal deploy "$MODAL_SCRIPT" 2>&1 | tee /dev/stderr || {
        error "Inference deployment failed"
    }
    info "Inference function deployed"
fi

# ── Deploy embeddings (sentence-transformers on T4) ────────────────
if [[ "$DEPLOY_ALL" == true ]] || [[ "$DEPLOY_EMBEDDINGS" == true ]]; then
    step "Deploying embeddings function (bge-m3 on T4)..."

    cd "$PROJECT_ROOT"
    modal deploy "$MODAL_SCRIPT" --function embeddings 2>&1 | tee /dev/stderr || {
        warn "Embeddings deployment failed — check Modal logs"
    }
    info "Embeddings function deployed"
fi

# ── Deploy training (QLoRA on A10G) ────────────────────────────────────
if [[ "$DEPLOY_ALL" == true ]] || [[ "$DEPLOY_TRAINING" == true ]]; then
    step "Deploying training function (QLoRA on A10G)..."

    TRAINING_SCRIPT="$PROJECT_ROOT/backend/app/services/modal_train.py"
    if [[ ! -f "$TRAINING_SCRIPT" ]]; then
        error "Modal training script not found at $TRAINING_SCRIPT"
    fi

    cd "$PROJECT_ROOT"
    modal deploy "$TRAINING_SCRIPT" 2>&1 | tee /dev/stderr || {
        error "Training deployment failed — check Modal logs"
    }
    info "Training function deployed"
fi

# ── Deploy reranker (cross-encoder on T4) ──────────────────────────────
if [[ "$DEPLOY_ALL" == true ]] || [[ "$DEPLOY_RERANKER" == true ]]; then
    step "Deploying reranker function (bge-reranker on T4)..."

    cd "$PROJECT_ROOT"
    modal deploy "$MODAL_SCRIPT" --function reranker 2>&1 | tee /dev/stderr || {
        warn "Reranker deployment failed — check Modal logs"
    }
    info "Reranker function deployed"
fi

# ── Verify deployments ─────────────────────────────────────────────
step "Verifying deployments..."

echo ""
info "All requested Modal functions deployed."
echo ""
info "  Monitor logs:"
info "    modal app logs idkp-production.inference"
info "    modal app logs idkp-production.embeddings"
info "    modal app logs idkp-production.reranker"
info "    modal app logs idkp-train.train_qlora_fn"
echo ""
info "  Check costs:  modal cost"
info "  App status:   ./scripts/runbooks/modal-deploy.sh --status"
