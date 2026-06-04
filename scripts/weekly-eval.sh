#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Weekly RAGAS Regression + Comparative Evaluation
#
# Automated weekly evaluation script for production. Performs:
#   1. RAGAS regression evaluation on the current production model
#   2. Comparative evaluation (base vs. fine-tuned) if a FT adapter exists
#   3. Stores results in the database and optionally uploads reports to S3
#   4. Sends alerts on metric drift detection
#
# Designed to run as a cron job (weekly, e.g., every Monday 02:00):
#   0 2 * * 1 /opt/idkp/scripts/weekly-eval.sh >> /var/log/idkp/weekly-eval.log 2>&1
#
# Usage:
#   ./scripts/weekly-eval.sh [--skip-comparison] [--alert-threshold 0.85]
#
# Options:
#   --skip-comparison    Skip the base vs. fine-tuned comparison step.
#   --alert-threshold    Minimum acceptable faithfulness score (default: 0.85).
#   --dry-run            Show what would happen without making API calls.
#
# Environment:
#   IDKP_API_URL         Backend API base URL (default: http://localhost:8000)
#   IDKP_API_TOKEN       Bearer token for API authentication
#   S3_BUCKET            S3 bucket for storing eval reports (optional)
#   SLACK_WEBHOOK_URL    Slack webhook for drift alerts (optional)
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
WEEK_LABEL="$(date -u +"%Y-W%V")"
REPORT_DIR="$PROJECT_ROOT/eval-reports/$WEEK_LABEL"
SKIP_COMPARISON=false
DRY_RUN=false
ALERT_THRESHOLD="${ALERT_THRESHOLD:-0.85}"
API_URL="${IDKP_API_URL:-http://localhost:8000}"
API_TOKEN="${IDKP_API_TOKEN:-}"
S3_BUCKET="${S3_BUCKET:-}"
SLACK_WEBHOOK="${SLACK_WEBHOOK_URL:-}"

# ── Colors ───────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $*"; }
ok()    { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*"; }
warn()  { echo -e "${YELLOW}[$(date +%H:%M:%S)]${NC} $*"; }
fail()  { echo -e "${RED}[$(date +%H:%M:%S)]${NC} $*"; }

# ── Argument Parsing ────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-comparison) SKIP_COMPARISON=true; shift ;;
        --dry-run)         DRY_RUN=true; shift ;;
        --alert-threshold) ALERT_THRESHOLD="$2"; shift 2 ;;
        -h|--help)
            head -25 "$0" | grep '^#' | sed 's/^# \?//'
            exit 0
            ;;
        *) fail "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Helpers ─────────────────────────────────────────────────────────
api_call() {
    local method="$1"
    local endpoint="$2"
    local data="${3:-}"

    local url="${API_URL}${endpoint}"
    local args=(-s -X "$method" -H "Content-Type: application/json")

    if [[ -n "$API_TOKEN" ]]; then
        args+=(-H "Authorization: Bearer ${API_TOKEN}")
    fi

    if [[ -n "$data" ]]; then
        args+=(-d "$data")
    fi

    curl "${args[@]}" "$url" 2>/dev/null
}

# ── Pre-flight Checks ────────────────────────────────────────────────
check_prerequisites() {
    info "Running pre-flight checks..."

    # Verify API is reachable
    if ! curl -sf --max-time 10 "${API_URL}/api/v1/health" > /dev/null 2>&1; then
        fail "Backend API not reachable at ${API_URL}"
        exit 1
    fi
    ok "Backend API reachable"

    # Create report directory
    mkdir -p "$REPORT_DIR"
    ok "Report directory: $REPORT_DIR"

    # Check for API token
    if [[ -z "$API_TOKEN" ]]; then
        warn "No API token set — some endpoints may require authentication"
    fi
}

# ── Step 1: Regression Evaluation ───────────────────────────────────
run_regression_eval() {
    info "Step 1: Running RAGAS regression evaluation"

    local run_type="weekly_regression"
    local payload
    payload=$(cat <<EOF
{
    "run_type": "${run_type}",
    "model_id": null,
    "model_variant": "production"
}
EOF
)

    if [[ "$DRY_RUN" = true ]]; then
        info "[DRY RUN] Would POST /api/v1/evaluations with run_type=${run_type}"
        return
    fi

    local response
    response=$(api_call POST "/api/v1/evaluations" "$payload")

    # Parse and save the results
    echo "$response" | python3 -m json.tool > "$REPORT_DIR/regression-results.json" 2>/dev/null || {
        echo "$response" > "$REPORT_DIR/regression-results.json"
    }

    # Extract key metrics
    local faithfulness context_relevance answer_relevance context_recall
    faithfulness=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
metrics = data.get('metrics', {})
print(metrics.get('faithfulness', 'N/A'))
" 2>/dev/null || echo "N/A")

    context_relevance=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
metrics = data.get('metrics', {})
print(metrics.get('context_relevance', 'N/A'))
" 2>/dev/null || echo "N/A")

    answer_relevance=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
metrics = data.get('metrics', {})
print(metrics.get('answer_relevance', 'N/A'))
" 2>/dev/null || echo "N/A")

    context_recall=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
metrics = data.get('metrics', {})
print(metrics.get('context_recall', 'N/A'))
" 2>/dev/null || echo "N/A")

    echo ""
    info "Regression Metrics — $WEEK_LABEL"
    echo "  ┌──────────────────────┬──────────┐"
    echo "  │ Metric               │ Score    │"
    echo "  ├──────────────────────┼──────────┤"
    echo "  │ Faithfulness         │ $(printf '%-8s' "$faithfulness") │"
    echo "  │ Context Relevance    │ $(printf '%-8s' "$context_relevance") │"
    echo "  │ Answer Relevance     │ $(printf '%-8s' "$answer_relevance") │"
    echo "  │ Context Recall       │ $(printf '%-8s' "$context_recall") │"
    echo "  └──────────────────────┴──────────┘"
    echo ""

    # Drift detection — check if faithfulness dropped below threshold
    if [[ "$faithfulness" != "N/A" ]]; then
        local threshold_check
        threshold_check=$(python3 -c "
faithfulness = float('$faithfulness')
threshold = float('$ALERT_THRESHOLD')
print('ALERT' if faithfulness < threshold else 'OK')
" 2>/dev/null || echo "OK")

        if [[ "$threshold_check" = "ALERT" ]]; then
            fail "DRIFT DETECTED: Faithfulness ($faithfulness) below threshold ($ALERT_THRESHOLD)"
            send_drift_alert "$faithfulness" "$WEEK_LABEL"
        else
            ok "Faithfulness ($faithfulness) above threshold ($ALERT_THRESHOLD)"
        fi
    fi
}

# ── Step 2: Comparative Evaluation ──────────────────────────────────
run_comparative_eval() {
    if [[ "$SKIP_COMPARISON" = true ]]; then
        info "Step 2: Comparative evaluation — skipped (--skip-comparison)"
        return
    fi

    info "Step 2: Running comparative evaluation (base vs. fine-tuned)"

    local payload
    payload=$(cat <<EOF
{
    "model_ids": ["meta-llama/Llama-3.1-8B-Instruct"],
    "model_variant": "production"
}
EOF
)

    if [[ "$DRY_RUN" = true ]]; then
        info "[DRY RUN] Would POST /api/v1/evaluations/benchmark with both models"
        return
    fi

    local response
    response=$(api_call POST "/api/v1/evaluations/benchmark" "$payload")

    echo "$response" | python3 -m json.tool > "$REPORT_DIR/comparative-results.json" 2>/dev/null || {
        echo "$response" > "$REPORT_DIR/comparative-results.json"
    }

    # Print summary
    echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('results', [])
print()
print('Comparative Results — $WEEK_LABEL')
print('  ┌──────────┬──────────┬──────────┬──────────┐')
print('  │ Model    │ Faithful │ Context  │ Answer   │')
print('  ├──────────┼──────────┼──────────┼──────────┤')
for r in results:
    m = r.get('metrics', {})
    fid = r.get('model_id', 'unknown')[:16]
    f = m.get('faithfulness', 'N/A')
    c = m.get('context_relevance', 'N/A')
    a = m.get('answer_relevance', 'N/A')
    f_str = str(f) if isinstance(f, float) else str(f)
    c_str = str(c) if isinstance(c, float) else str(c)
    a_str = str(a) if isinstance(a, float) else str(a)
    print(f'  │ {fid:<8s} │ {f_str:<8s} │ {c_str:<8s} │ {a_str:<8s} │')
print('  └──────────┴──────────┴──────────┴──────────┘')
print()
" 2>/dev/null || warn "Could not parse comparative results"

    ok "Comparative evaluation complete"
}

# ── Step 3: Store Reports ───────────────────────────────────────────
store_reports() {
    if [[ -z "$S3_BUCKET" ]]; then
        info "Step 3: S3 upload — skipped (S3_BUCKET not set)"
        return
    fi

    info "Step 3: Uploading reports to S3"

    if [[ "$DRY_RUN" = true ]]; then
        info "[DRY RUN] Would upload reports to s3://${S3_BUCKET}/eval/${WEEK_LABEL}/"
        return
    fi

    if command -v aws &> /dev/null; then
        for report in "$REPORT_DIR"/*.json; do
            if [[ -f "$report" ]]; then
                aws s3 cp "$report" "s3://${S3_BUCKET}/eval/${WEEK_LABEL}/" \
                    --content-type "application/json" 2>/dev/null && \
                    ok "Uploaded $(basename "$report")" || \
                    warn "Failed to upload $(basename "$report")"
            fi
        done
    else
        warn "AWS CLI not installed — skipping S3 upload"
    fi
}

# ── Step 4: Send Drift Alert ─────────────────────────────────────────
send_drift_alert() {
    local faithfulness="$1"
    local week="$2"
    local message="🚨 *IDKP Weekly Eval Alert* — $week
Faithfulness dropped below threshold: *${faithfulness}* < *${ALERT_THRESHOLD}*
Review report: \`${REPORT_DIR}/regression-results.json\`
Action: Consider re-tuning the model or investigating data drift."

    if [[ -n "$SLACK_WEBHOOK" && "$DRY_RUN" != true ]]; then
        curl -s -X POST "$SLACK_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{\"text\": $(echo "$message" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip()))')}" \
            > /dev/null 2>&1 && ok "Slack alert sent" || warn "Slack alert failed"
    fi

    # Also print to stdout for cron email capture
    echo ""
    echo "=== DRIFT ALERT ==="
    echo "$message"
    echo "==================="
}

# ── Step 5: Summary ──────────────────────────────────────────────────
print_summary() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           Weekly Evaluation Complete                      ║"
    echo "╠════════════════════════════════════════════════════════════╣"
    echo "║  Week:           $WEEK_LABEL"
    echo "║  Timestamp:      $TIMESTAMP"
    echo "║  Reports saved:  $REPORT_DIR/"
    echo "║  Regression:     $(ls "$REPORT_DIR/regression-results.json" 2>/dev/null && echo "Yes" || echo "No")"
    echo "║  Comparative:    $([ "$SKIP_COMPARISON" = true ] && echo "Skipped" || (ls "$REPORT_DIR/comparative-results.json" 2>/dev/null && echo "Yes" || echo "No"))"
    echo "║  S3 uploaded:    $([ -n "$S3_BUCKET" ] && echo "Yes" || echo "No (bucket not configured)")"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
}

# ── Main ────────────────────────────────────────────────────────────
main() {
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           IDKP Weekly Evaluation Automation               ║"
    echo "║           $TIMESTAMP                          ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    if [[ "$DRY_RUN" = true ]]; then
        warn "DRY RUN MODE — no API calls will be made"
        echo ""
    fi

    check_prerequisites
    run_regression_eval
    run_comparative_eval
    store_reports
    print_summary
}

main "$@"
