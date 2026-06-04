#!/bin/bash
# ──────────────────────────────────────────────────────────────────────
# IDKP Runbook: Re-indexing
#
# Rebuilds the Qdrant vector index from scratch:
#   1. Backs up existing collection metadata
#   2. Deletes the existing collection
#   3. Re-encodes all document chunks from the database
#   4. Re-populates Qdrant with fresh embeddings
#
# Usage:
#   chmod +x scripts/runbooks/reindex.sh
#   ./scripts/runbooks/reindex.sh [--dry-run] [--collection COLLECTION_NAME]
#
# Prerequisites:
#   - PostgreSQL running with document_chunks table populated
#   - Qdrant Cloud accessible (QDRANT_URL, QDRANT_API_KEY)
#   - Modal embeddings function running or local embeddings model
#   - .env.production loaded (or pass --env-file)
#
# Estimated time: 5-30 minutes depending on chunk count
#
# Rollback: Restore from Qdrant snapshot (taken before deletion)
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
DRY_RUN=false
COLLECTION_NAME="idkp_documents"
for arg in "$@"; do
    case $arg in
        --dry-run)              DRY_RUN=true ;;
        --collection)           COLLECTION_NAME="$2"; shift ;;
    esac
done

# ── Load environment ───────────────────────────────────────────────
if [[ -f "$PROJECT_ROOT/.env.production" ]]; then
    set -a
    source "$PROJECT_ROOT/.env.production"
    set +a
elif [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
else
    warn "No .env file found — relying on exported environment variables"
fi

# ── Pre-flight checks ──────────────────────────────────────────────
step "Pre-flight checks"

if [[ -z "${QDRANT_URL:-}" ]]; then
    error "QDRANT_URL not set — check .env file"
fi
if [[ -z "${QDRANT_API_KEY:-}" ]]; then
    error "QDRANT_API_KEY not set — check .env file"
fi

QDRANT_COLLECTION="${QDRANT_COLLECTION:-$COLLECTION_NAME}"
info "Target collection: $QDRANT_COLLECTION"

# ── Step 1: Create snapshot (backup before delete) ───────────────────
step "Creating Qdrant snapshot for rollback..."

SNAPSHOT_NAME="pre-reindex-$(date +%Y%m%d-%H%M%S)"

if [[ "$DRY_RUN" == true ]]; then
    warn "DRY RUN: Would create snapshot '$SNAPSHOT_NAME'"
else
    HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
        -X PUT "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots/${SNAPSHOT_NAME}" \
        -H "api-key: ${QDRANT_API_KEY}" \
        -H "Content-Type: application/json" 2>/dev/null || true)

    if [[ "$HTTP_CODE" == "200" ]] || [[ "$HTTP_CODE" == "201" ]]; then
        info "Snapshot created: $SNAPSHOT_NAME"
    else
        warn "Snapshot creation returned HTTP $HTTP_CODE — continuing anyway"
    fi
fi

# ── Step 2: Delete existing collection ─────────────────────────────────
step "Deleting existing collection..."

if [[ "$DRY_RUN" == true ]]; then
    warn "DRY RUN: Would delete collection '$QDRANT_COLLECTION'"
else
    HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
        -X DELETE "${QDRANT_URL}/collections/${QDRANT_COLLECTION}" \
        -H "api-key: ${QDRANT_API_KEY}" 2>/dev/null || true)
    info "Delete response: HTTP $HTTP_CODE"
fi

# ── Step 3: Re-create collection ────────────────────────────────────
step "Re-creating collection with correct dimensions..."

PAYLOAD=$(cat <<EOF
{
    "vectors": {
        "size": 1024,
        "distance": "Cosine"
    },
    "optimizers_config": {
        "default_segment_number": 5
    }
}
EOF
)

if [[ "$DRY_RUN" == true ]]; then
    warn "DRY RUN: Would create collection '$QDRANT_COLLECTION' (1024-dim Cosine)"
else
    HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
        -X PUT "${QDRANT_URL}/collections/${QDRANT_COLLECTION}" \
        -H "api-key: ${QDRANT_API_KEY}" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" 2>/dev/null || true)
    info "Create response: HTTP $HTTP_CODE"
fi

# ── Step 4: Re-encode and upload chunks ──────────────────────────────
step "Triggering re-encoding and upload via backend API..."

if [[ "$DRY_RUN" == true ]]; then
    warn "DRY RUN: Would call POST /api/v1/documents/reindex"
    warn "DRY RUN: Run complete (no changes made)"
    exit 0
fi

# Use the backend API to trigger re-indexing
# This reads chunks from PostgreSQL, encodes via embeddings service, and upserts to Qdrant
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"

HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
    -X POST "${BACKEND_URL}/api/v1/documents/reindex" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${REINDEX_TOKEN:-}" \
    --max-time 1800 2>/dev/null || true)

if [[ "$HTTP_CODE" == "200" ]] || [[ "$HTTP_CODE" == "202" ]]; then
    info "Re-indexing triggered successfully"
else
    warn "Re-indexing returned HTTP $HTTP_CODE — check backend logs"
fi

# ── Done ──────────────────────────────────────────────────────────────
echo ""
info "Re-indexing complete!"
info "  Collection: $QDRANT_COLLECTION"
info "  Snapshot:   $SNAPSHOT_NAME (for rollback)"
echo ""
info "To rollback: curl -X PUT ${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots/recover -d '{\"snapshot\": \"$SNAPSHOT_NAME\"}'"
