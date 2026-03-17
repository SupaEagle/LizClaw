#!/bin/bash
# Cron Wrapper Script for OpenClaw
# Usage: ./cron-wrapper.sh <job_name> <command> [options]
# Options:
#   --frequency daily|hourly    How often to run (default: daily)
#   --timeout SECONDS           Job timeout
#   --no-idempotency           Skip idempotency check
#   --notify                   Send notification on failure

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_PY="$SCRIPT_DIR/cron.py"

# Parse arguments
JOB_NAME=""
COMMAND=""
FREQUENCY="daily"
TIMEOUT=""
NO_IDEMPOTENCY=""
NOTIFY=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --frequency)
            FREQUENCY="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --no-idempotency)
            NO_IDEMPOTENCY="--no-idempotency"
            shift
            ;;
        --notify)
            NOTIFY="1"
            shift
            ;;
        *)
            if [[ -z "$JOB_NAME" ]]; then
                JOB_NAME="$1"
            elif [[ -z "$COMMAND" ]]; then
                COMMAND="$1"
            fi
            shift
            ;;
    esac
done

if [[ -z "$JOB_NAME" || -z "$COMMAND" ]]; then
    echo "Usage: $0 <job_name> <command> [--frequency daily|hourly] [--timeout SECONDS] [--no-idempotency] [--notify]"
    exit 1
fi

# Build command args
ARGS=("run" "$JOB_NAME" "$COMMAND")
[[ -n "$FREQUENCY" ]] && ARGS+=("--frequency" "$FREQUENCY")
[[ -n "$TIMEOUT" ]] && ARGS+=("--timeout" "$TIMEOUT")
[[ -n "$NO_IDEMPOTENCY" ]] && ARGS+=("$NO_IDEMPOTENCY")

# Run via Python cron system
OUTPUT=$(python3 "$CRON_PY" "${ARGS[@]}" 2>&1)
EXIT_CODE=$?

# Parse output for status
if echo "$OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('success') or d.get('skipped') else 1)" 2>/dev/null; then
    echo "$OUTPUT"
    exit 0
else
    echo "$OUTPUT"
    
    # Handle notifications
    if [[ -n "$NOTIFY" ]] && [[ $EXIT_CODE -ne 0 ]]; then
        # Check for persistent failures
        if echo "$OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('persistent_failure') else 1)" 2>/dev/null; then
            ALERT=$(echo "$OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('failure_alert',''))")
            echo "🔴 PERSISTENT FAILURE ALERT: $ALERT" >&2
        fi
    fi
    
    exit $EXIT_CODE
fi
