#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Production Rollback Runbook
#
# Safely revert the production deployment to a previous state.
# Supports:
#   - Git checkout to a previous commit
#   - Alembic database downgrade (by N steps or to a specific revision)
#   - Qdrant vector store snapshot restoration
#   - Container restart with the rolled-back code
#
# Usage:
#   ./scripts/runbooks/rollback.sh --confirm [--git-ref REF] \
#       [--db-steps N] [--db-revision REV] [--qdrant-snapshot SNAPSHOT_ID]
#
# Options:
#   --confirm          Required. Must be passed to prevent accidental rollback.
#   --git-ref REF      Git ref to rollback to (default: HEAD~1).
#   --db-steps N       Number of Alembic migration steps to downgrade (default: 1).
#   --db-revision REV  Target Alembic revision ID instead of step count.
#   --qdrant-snapshot  Qdrant snapshot ID to restore (skipped if omitted).
#   --dry-run          Show what would happen without making changes.
#
# Examples:
#   # Quick rollback: revert last commit, downgrade 1 migration, restart
#   ./scripts/runbooks/rollback.sh --confirm
#
#   # Rollback to specific commit with 3 migration steps
#   ./scripts/runbooks/rollback.sh --confirm --git-ref abc123f --db-steps 3
#
#   # Database-only rollback to a specific revision
#   ./scripts/runbooks/rollback.sh --confirm --db-revision a3b7c9d2e4f5
#
#   # Dry run to preview actions
#   ./scripts/runbooks/rollback.sh --dry-run --git-ref HEAD~2 --db-steps 2
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.prod.yml"
ENV_FILE="$PROJECT_ROOT/.env.production"
AUDIT_LOG="$PROJECT_ROOT/logs/rollback-audit.log"
CONFIRMED=false
DRY_RUN=false
GIT_REF="HEAD~1"
DB_STEPS=""
DB_REVISION=""
QDRANT_SNAPSHOT=""
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# ── Colors ───────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }

# ── Argument Parsing ────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --confirm)        CONFIRMED=true; shift ;;
        --dry-run)        DRY_RUN=true; shift ;;
        --git-ref)        GIT_REF="$2"; shift 2 ;;
        --db-steps)        DB_STEPS="$2"; shift 2 ;;
        --db-revision)     DB_REVISION="$2"; shift 2 ;;
        --qdrant-snapshot) QDRANT_SNAPSHOT="$2"; shift 2 ;;
        -h|--help)
            head -30 "$0" | grep '^#' | sed 's/^# \?//'
            exit 0
            ;;
        *) fail "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Pre-flight Checks ─────────────────────────────────────────────────
check_prerequisites() {
    info "Running pre-flight checks..."

    # Verify confirmation flag
    if [[ "$CONFIRMED" != true && "$DRY_RUN" != true ]]; then
        fail "This script performs a production rollback."
        echo ""
        fail "To proceed, you MUST pass --confirm."
        fail "Use --dry-run first to preview the planned actions."
        echo ""
        echo "  $0 --dry-run --git-ref abc123f --db-steps 1"
        echo "  $0 --confirm --git-ref abc123f --db-steps 1"
        exit 1
    fi

    # Verify inside git repo
    if ! git -C "$PROJECT_ROOT" rev-parse --git-dir > /dev/null 2>&1; then
        fail "Not inside a git repository: $PROJECT_ROOT"
        exit 1
    fi

    # Verify Docker Compose file exists
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        fail "Production compose file not found: $COMPOSE_FILE"
        exit 1
    fi

    # Verify env file exists
    if [[ ! -f "$ENV_FILE" ]]; then
        fail "Production env file not found: $ENV_FILE"
        exit 1
    fi

    # Verify git ref is valid
    if ! git -C "$PROJECT_ROOT" rev-parse --verify "$GIT_REF" > /dev/null 2>&1; then
        fail "Invalid git ref: $GIT_REF"
        exit 1
    fi

    # Verify Docker is available
    if ! command -v docker &> /dev/null; then
        fail "Docker is not installed or not in PATH"
        exit 1
    fi

    # Verify Docker Compose plugin is available
    if ! docker compose version &> /dev/null; then
        fail "Docker Compose plugin is not available"
        exit 1
    fi

    ok "All pre-flight checks passed"
}

# ── Audit Logging ───────────────────────────────────────────────────
log_audit() {
    local action="$1"
    local detail="$2"
    local entry="{\"timestamp\":\"$TIMESTAMP\",\"action\":\"$action\",\"detail\":\"$detail\",\"git_ref\":\"$GIT_REF\",\"user\":\"$(whoami)\"}"

    mkdir -p "$(dirname "$AUDIT_LOG")"
    echo "$entry" >> "$AUDIT_LOG"
    info "Audit: $action — $detail"
}

# ── Display Rollback Plan ────────────────────────────────────────────
show_plan() {
    local current_ref
    current_ref=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD)
    local target_ref
    target_ref=$(git -C "$PROJECT_ROOT" rev-parse --short "$GIT_REF")

    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           PRODUCTION ROLLBACK PLAN                        ║"
    echo "╠════════════════════════════════════════════════════════════╣"
    echo "║  Current commit:  $current_ref                             "
    echo "║  Target commit:   $target_ref                             "
    echo "║  DB downgrade:    $([ -n "$DB_STEPS" ] && echo "$DB_STEPS step(s)" || ([ -n "$DB_REVISION" ] && echo "revision $DB_REVISION" || echo "1 step (default))")"
    echo "║  Qdrant snapshot: $([ -n "$QDRANT_SNAPSHOT" ] && echo "$QDRANT_SNAPSHOT" || echo "Skip")"
    echo "║  Mode:            $([ "$DRY_RUN" = true ] && echo "DRY RUN" || echo "LIVE")"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
}

# ── Step 1: Git Rollback ────────────────────────────────────────────
rollback_git() {
    info "Step 1: Git rollback to $GIT_REF"

    if [[ "$DRY_RUN" = true ]]; then
        info "[DRY RUN] Would run: git checkout $GIT_REF"
        return
    fi

    # Stash any uncommitted changes first
    if ! git -C "$PROJECT_ROOT" diff --quiet 2>/dev/null || \
       ! git -C "$PROJECT_ROOT" diff --cached --quiet 2>/dev/null; then
        warn "Uncommitted changes detected — stashing before rollback"
        git -C "$PROJECT_ROOT" stash push -m "auto-stash before rollback to $GIT_REF"
    fi

    git -C "$PROJECT_ROOT" checkout "$GIT_REF"
    log_audit "git_checkout" "Rolled back from $current_ref to $(git -C "$PROJECT_ROOT" rev-parse --short HEAD)"
    ok "Git checkout complete: $(git -C "$PROJECT_ROOT" rev-parse --short HEAD)"
}

# ── Step 2: Database Rollback ───────────────────────────────────────
rollback_database() {
    info "Step 2: Database migration rollback"

    if [[ "$DRY_RUN" = true ]]; then
        if [[ -n "$DB_REVISION" ]]; then
            info "[DRY RUN] Would run: docker compose exec backend alembic downgrade $DB_REVISION"
        elif [[ -n "$DB_STEPS" ]]; then
            info "[DRY RUN] Would run: docker compose exec backend alembic downgrade -$DB_STEPS"
        else
            info "[DRY RUN] Would run: docker compose exec backend alembic downgrade -1"
        fi
        return
    fi

    local downgrade_cmd=""
    if [[ -n "$DB_REVISION" ]]; then
        downgrade_cmd="alembic downgrade $DB_REVISION"
    elif [[ -n "$DB_STEPS" ]]; then
        downgrade_cmd="alembic downgrade -$DB_STEPS"
    else
        downgrade_cmd="alembic downgrade -1"
    fi

    info "Running: $downgrade_cmd"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
        exec -T backend $downgrade_cmd

    log_audit "db_downgrade" "Ran: $downgrade_cmd"
    ok "Database rollback complete"
}

# ── Step 3: Qdrant Snapshot Restore ─────────────────────────────────
rollback_qdrant() {
    if [[ -z "$QDRANT_SNAPSHOT" ]]; then
        info "Step 3: Qdrant restore — skipped (no snapshot specified)"
        return
    fi

    info "Step 3: Restoring Qdrant snapshot $QDRANT_SNAPSHOT"

    # Read Qdrant config from env
    local qdrant_url qdrant_collection
    qdrant_url="$(grep -E '^QDRANT_URL=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' || echo "http://localhost:6333")"
    qdrant_collection="$(grep -E '^QDRANT_COLLECTION=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' || echo "idkp_chunks")"

    if [[ "$DRY_RUN" = true ]]; then
        info "[DRY RUN] Would restore Qdrant snapshot $QDRANT_SNAPSHOT on collection $qdrant_collection"
        return
    fi

    # Create a new collection from the snapshot
    # First, delete the existing collection
    warn "Deleting collection '$qdrant_collection' before snapshot restore..."
    curl -s -X DELETE "${qdrant_url}/collections/${qdrant_collection}" > /dev/null || true

    # Restore from snapshot
    curl -s -X PUT \
        "${qdrant_url}/collections/${qdrant_collection}/snapshots/${QDRANT_SNAPSHOT}/recover" \
        -H "Content-Type: application/json" \
        -d "{\"location\": \"snapshot_${QDRANT_SNAPSHOT}\"}" \
        | python3 -m json.tool 2>/dev/null || true

    log_audit "qdrant_restore" "Restored snapshot $QDRANT_SNAPSHOT on collection $qdrant_collection"
    ok "Qdrant snapshot restore complete"
}

# ── Step 4: Restart Services ────────────────────────────────────────
restart_services() {
    info "Step 4: Restarting production services"

    if [[ "$DRY_RUN" = true ]]; then
        info "[DRY RUN] Would run: docker compose down && docker compose up -d"
        return
    fi

    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --wait

    log_audit "services_restart" "Restarted all production containers after rollback"
    ok "Services restarted"
}

# ── Step 5: Health Verification ─────────────────────────────────────
verify_health() {
    info "Step 5: Verifying system health"

    local base_url
    base_url="$(grep -E '^PROD_DOMAIN=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' || echo "http://localhost")"
    local errors=0

    # Check backend health
    if curl -sf --max-time 15 "${base_url}/api/v1/health" > /dev/null 2>&1; then
        ok "Backend health check: OK"
    else
        fail "Backend health check: FAILED"
        ((errors++))
    fi

    # Check frontend
    if curl -sf --max-time 15 "${base_url}/" > /dev/null 2>&1; then
        ok "Frontend: OK"
    else
        fail "Frontend: FAILED"
        ((errors++))
    fi

    # Check docs endpoint
    if curl -sf --max-time 15 "${base_url}/docs" > /dev/null 2>&1; then
        ok "API docs: OK"
    else
        warn "API docs: unreachable (non-critical)"
    fi

    if [[ "$errors" -gt 0 ]]; then
        fail "Rollback completed with $errors health check failure(s)"
        log_audit "health_check" "FAILED with $errors errors after rollback"
        return 1
    fi

    log_audit "health_check" "All health checks passed after rollback"
    ok "All health checks passed — rollback successful"
}

# ── Main ────────────────────────────────────────────────────────────
main() {
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           IDKP Production Rollback Runbook                ║"
    echo "║           $TIMESTAMP                          ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    check_prerequisites
    show_plan

    if [[ "$DRY_RUN" = true ]]; then
        warn "DRY RUN MODE — no changes will be made"
        echo ""
    fi

    rollback_git
    rollback_database
    rollback_qdrant
    restart_services
    verify_health

    echo ""
    ok "Rollback complete. Review the audit log at: $AUDIT_LOG"
    echo ""
    info "To view rollback history:"
    echo "  cat $AUDIT_LOG | python3 -m json.tool --no-ensure-ascii"
}

main "$@"
