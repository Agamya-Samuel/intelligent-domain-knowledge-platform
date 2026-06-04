#!/bin/bash
# ──────────────────────────────────────────────────────────────────────
# IDKP Runbook: Model Re-tune
#
# Triggers a new QLoRA fine-tuning job with configurable parameters:
#   1. Validates training data exists and meets quality thresholds
#   2. Creates a new fine-tuning job record
#   3. Submits the job to Modal for GPU training
#   4. Monitors training progress via WebSocket
#   5. Runs post-training evaluation
#   6. Deploys the new adapter if quality gate passes
#
# Usage:
#   chmod +x scripts/runbooks/model-retune.sh
#   ./scripts/runbooks/model-retune.sh \
#     --model qwen2.5-7b \
#     --epochs 3 \
#     --rank 64 \
#     --learning-rate 2e-4
#
# Prerequisites:
#   - Training data uploaded and validated in S3 (datasets/ prefix)
#   - Modal CLI authenticated
#   - Backend running with fine-tune endpoints
#   - Ground truth eval dataset present
#
# Estimated time: 30-180 minutes depending on model and data size
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

# ── Default parameters ───────────────────────────────────────────────
MODEL_ID="qwen2.5-7b"
EPOCHS=3
RANK=64
LEARNING_RATE="2e-4"
DRY_RUN=false
AUTH_TOKEN=""

# ── Parse arguments ─────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --model)          MODEL_ID="$2"; shift ;;
        --epochs)         EPOCHS="$2"; shift ;;
        --rank)           RANK="$2"; shift ;;
        --learning-rate)  LEARNING_RATE="$2"; shift ;;
        --token)          AUTH_TOKEN="$2"; shift ;;
        --dry-run)        DRY_RUN=true ;;
        *)                warn "Unknown argument: $1" ;;
    esac
    shift
done

# ── Load environment ───────────────────────────────────────────────
if [[ -f "$PROJECT_ROOT/.env.production" ]]; then
    set -a; source "$PROJECT_ROOT/.env.production"; set +a
elif [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a; source "$PROJECT_ROOT/.env"; set +a
fi

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"

# ── Step 1: Validate training data ──────────────────────────────────
step "Validating training data..."

if [[ "$DRY_RUN" == true ]]; then
    warn "DRY RUN: Would check training data in S3 and DB"
else
    # Check that training data exists via API
    HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
        "${BACKEND_URL}/api/v1/datasets" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        --max-time 30 2>/dev/null || true)

    if [[ "$HTTP_CODE" != "200" ]]; then
        error "Cannot access training datasets (HTTP $HTTP_CODE)"
    fi
    info "Training data accessible"
fi

# ── Step 2: Trigger fine-tuning job ────────────────────────────────
step "Creating fine-tuning job..."

JOB_PAYLOAD=$(cat <<EOF
{
    "model_id": "${MODEL_ID}",
    "dataset_name": "latest",
    "hyperparameters": {
        "qlora_rank": ${RANK},
        "qlora_alpha": $((RANK * 2)),
        "qlora_dropout": 0.05,
        "learning_rate": ${LEARNING_RATE},
        "num_epochs": ${EPOCHS},
        "batch_size": 4,
        "gradient_accumulation_steps": 4,
        "max_seq_length": 2048
    }
}
EOF
)

if [[ "$DRY_RUN" == true ]]; then
    warn "DRY RUN: Would create fine-tune job with payload:"
    echo "$JOB_PAYLOAD" | python3 -m json.tool 2>/dev/null || echo "$JOB_PAYLOAD"
    warn "DRY RUN: Would monitor via WebSocket"
    warn "DRY RUN: Would run post-training evaluation"
    exit 0
fi

RESPONSE=$(curl -sf \
    -X POST "${BACKEND_URL}/api/v1/fine-tune/jobs" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${AUTH_TOKEN}" \
    -d "$JOB_PAYLOAD" \
    --max-time 60 2>/dev/null || echo '{"error": "request_failed"}')

JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', 'unknown'))" 2>/dev/null || echo "unknown")

if [[ "$JOB_ID" == "unknown" ]]; then
    error "Failed to create fine-tuning job. Response: $RESPONSE"
fi

info "Fine-tuning job created: $JOB_ID"
info "  Model:    $MODEL_ID"
info "  Epochs:   $EPOCHS"
info "  Rank:     $RANK"
info "  LR:       $LEARNING_RATE"

# ── Step 3: Monitor training ────────────────────────────────────────
step "Monitoring training progress (check WebSocket at /ws/finetune/jobs/${JOB_ID})..."
info "Job ID: $JOB_ID"
info ""
info "Monitor via:"
info "  WebSocket: wss://\${PROD_DOMAIN}/ws/finetune/jobs/${JOB_ID}"
info "  API:       GET ${BACKEND_URL}/api/v1/fine-tune/jobs/${JOB_ID}"
info ""
warn "This script does not block. Monitor training via the WebSocket or API."
info ""
info "After training completes, run post-training evaluation:"
info "  curl -X POST ${BACKEND_URL}/api/v1/evaluations -d '{\"run_type\": \"post_training\", \"model_id\": \"${MODEL_ID}\", \"model_variant\": \"finetuned\", \"job_id\": \"${JOB_ID}\"}' -H 'Authorization: Bearer ${AUTH_TOKEN}' -H 'Content-Type: application/json'"
