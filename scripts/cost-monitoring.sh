#!/bin/bash
# ──────────────────────────────────────────────────────────────────────
# IDKP Cost Monitoring Script
#
# Checks Modal and S3 usage against budget thresholds and sends alerts.
# Designed to run as a cron job (hourly or daily).
#
# Usage:
#   chmod +x scripts/cost-monitoring.sh
#   ./scripts/cost-monitoring.sh [--check-only]
#
# Cron (hourly):
#   0 * * * * /path/to/scripts/cost-monitoring.sh >> /var/log/idkp-cost-monitor.log 2>&1
#
# Alert channels (configurable):
#   - stdout (default — useful for log aggregation)
#   - Slack webhook (optional, set COST_ALERT_WEBHOOK_URL)
#   - Email (optional, set COST_ALERT_EMAIL)
#
# Budget thresholds:
#   - 80% warning ($24 of $30 monthly budget)
#   - 95% critical ($28.50 of $30 monthly budget)
#   - 100% hard block (alert only — hard block enforced by backend)
# ──────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Colors ───────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[$(date -u '+%Y-%m-%dT%H:%M:%SZ')]${NC} $*"; }
warn()  { echo -e "${YELLOW}[$(date -u '+%Y-%m-%dT%H:%M:%SZ')]${NC} $*"; }
alert() { echo -e "${RED}[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] ALERT${NC} $*"; }

# ── Configuration ───────────────────────────────────────────────────
BUDGET_MONTHLY=${BUDGET_MONTHLY_LIMIT:-30.00}
WARN_THRESHOLD=0.80    # 80% — $24
CRITICAL_THRESHOLD=0.95 # 95% — $28.50
HARD_BLOCK_THRESHOLD=1.00 # 100% — $30

CHECK_ONLY=false
for arg in "$@"; do
    case $arg in
        --check-only) CHECK_ONLY=true ;;
    esac
done

# ── Load environment ───────────────────────────────────────────────
if [[ -f "$PROJECT_ROOT/.env.production" ]]; then
    set -a
    source "$PROJECT_ROOT/.env.production"
    set +a
fi

# ── Helper: send alert ─────────────────────────────────────────────
send_alert() {
    local severity="$1"
    local message="$2"

    echo "$message"

    # Slack webhook (optional)
    if [[ -n "${COST_ALERT_WEBHOOK_URL:-}" ]]; then
        local payload
        payload=$(cat <<EOF
{"text":"[$severity] IDKP Cost Alert\n$message"}
EOF
        )
        curl -sf -X POST -H "Content-Type: application/json" \
            -d "$payload" "$COST_ALERT_WEBHOOK_URL" 2>/dev/null || true
    fi

    # Email (optional — requires mailutils or sendmail)
    if [[ -n "${COST_ALERT_EMAIL:-}" ]] && command -v mail &>/dev/null; then
        echo "$message" | mail -s "[$severity] IDKP Cost Alert" "$COST_ALERT_EMAIL" 2>/dev/null || true
    fi
}

# ── Step 1: Check Modal.com usage ───────────────────────────────────
info "Checking Modal.com GPU usage..."

MODAL_COST=0.00
MODAL_ALERT=false

if command -v modal &>/dev/null; then
    # Modal CLI usage summary (last 30 days)
    MODAL_COST=$(modal cost 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1 || echo "0.00")
else
    warn "Modal CLI not available — skipping Modal cost check"
fi

MODAL_COST=$(echo "$MODAL_COST" | awk '{printf "%.2f", $0}')
MODAL_PCT=$(echo "$MODAL_COST $BUDGET_MONTHLY" | awk '{printf "%.0f", ($1 / $2) * 100}')

if (( $(echo "$MODAL_PCT >= $((WARN_THRESHOLD * 100))" | bc -l 2>/dev/null || echo 0) )); then
    MODAL_ALERT=true
    alert "Modal GPU cost: \$$MODAL_COST ($MODAL_PCT% of \$$BUDGET_MONTHLY budget)"
else
    info "  Modal GPU cost: \$$MODAL_COST ($MODAL_PCT% of budget) — OK"
fi

# ── Step 2: Check S3 usage ──────────────────────────────────────────
info "Checking AWS S3 storage usage..."

S3_COST=0.00
S3_SIZE_GB=0

if [[ -n "${AWS_ACCESS_KEY_ID:-}" ]] && command -v aws &>/dev/null; then
    BUCKET="${S3_BUCKET_NAME:-idkp-documents-prod}"
    S3_SIZE_GB=$(aws s3api list-objects-v2 \
        --bucket "$BUCKET" \
        --query "sum(Contents[].Size)" \
        --output text 2>/dev/null | awk '{printf "%.2f", $1 / 1073741824}' || echo "0")

    # Estimate cost: S3 Standard = $0.023/GB/month
    S3_COST=$(echo "$S3_SIZE_GB 0.023" | awk '{printf "%.2f", $1 * $2}')
    info "  S3 storage: ${S3_SIZE_GB}GB (est. \$$S3_COST/month)"
else
    warn "  AWS CLI not configured — skipping S3 cost check"
fi

# ── Step 3: Total cost assessment ───────────────────────────────────
TOTAL_COST=$(echo "$MODAL_COST $S3_COST" | awk '{printf "%.2f", $1 + $2}')
TOTAL_PCT=$(echo "$TOTAL_COST $BUDGET_MONTHLY" | awk '{printf "%.0f", ($1 / $2) * 100}')

info "Total estimated cost: \$$TOTAL_COST ($TOTAL_PCT% of \$$BUDGET_MONTHLY monthly budget)"

# ── Step 4: Evaluate thresholds ─────────────────────────────────────
if (( $(echo "$TOTAL_PCT >= 95" | bc -l 2>/dev/null || echo 0) )); then
    send_alert "CRITICAL" "IDKP cost at ${TOTAL_PCT}% of monthly budget (\$$TOTAL_COST / \$$BUDGET_MONTHLY). Modal: \$$MODAL_COST, S3: \$$S3_COST. Immediate action required."
elif (( $(echo "$TOTAL_PCT >= 80" | bc -l 2>/dev/null || echo 0) )); then
    send_alert "WARNING" "IDKP cost at ${TOTAL_PCT}% of monthly budget (\$$TOTAL_COST / \$$BUDGET_MONTHLY). Modal: \$$MODAL_COST, S3: \$$S3_COST. Consider reducing usage."
else
    info "Cost within acceptable range"
fi

# ── Step 5: Report summary ─────────────────────────────────────────
info "Cost monitoring summary:"
info "  Modal GPU:     \$$MODAL_COST"
info "  S3 Storage:   \$$S3_COST (${S3_SIZE_GB}GB)"
info "  Total:         \$$TOTAL_COST / \$$BUDGET_MONTHLY ($TOTAL_PCT%)"
info "  Next check:    1 hour"
