#!/usr/bin/env bash
set -euo pipefail

# Duty Analyze CLI — investigate on-call duty tickets via YQL queries
# Looks up appmetrica_device_id, fetches mobile logs, analyzes events

QUERIES_DIR="$HOME/.claude/skills/duty-analyze/queries"
YQL_CLI="$HOME/.claude/bin/yql-cli.sh"
TRACKER_CLI="$HOME/.claude/bin/tracker-cli.sh"

# --- Helpers ---
render_template() {
  local template="$1"
  shift
  local content
  content=$(cat "$template")

  # Replace {{KEY}} placeholders with provided key=value pairs
  while [[ $# -gt 0 ]]; do
    local key="${1%%=*}"
    local value="${1#*=}"
    content="${content//\{\{$key\}\}/$value}"
    shift
  done

  echo "$content"
}

usage() {
  cat <<'USAGE'
Duty Analyze CLI — investigate on-call duty tickets

Usage: duty-analyze-cli.sh <command> [options]

Commands:
  get-device-id     Get appmetrica_device_id by executorId and date
  get-mobile-logs   Get mobile app event logs by device ID and date
  analyze-ticket    Full analysis: ticket → device ID → logs

Options for get-device-id:
  --executor-id UUID    Executor UUID (required)
  --date YYYY-MM-DD     Event date (required)

Options for get-mobile-logs:
  --device-id ID        AppMetrica device ID (required)
  --date YYYY-MM-DD     Event date (required)
  --datetime DATETIME   Filter events after this datetime (optional)
  --api-key KEY         APIKey (default: 3324463 = flutter testing)
  --event-name PATTERN  Filter by event name pattern (optional)

Options for analyze-ticket:
  --ticket KEY          Tracker ticket key (required)
  --executor-id UUID    Executor UUID (required)
  --date YYYY-MM-DD     Event date (required)

API Keys reference:
  2998081  = iOS/Android prod
  3324463  = Flutter testing
  121179   = Android pro
  288312   = Android testing

Examples:
  duty-analyze-cli.sh get-device-id --executor-id abc123 --date 2026-03-15
  duty-analyze-cli.sh get-mobile-logs --device-id DEV_ID --date 2026-03-15
  duty-analyze-cli.sh get-mobile-logs --device-id DEV_ID --date 2026-03-15 --datetime "2026-03-15 14:00:00"
  duty-analyze-cli.sh analyze-ticket --ticket TICKET-123 --executor-id abc123 --date 2026-03-15
USAGE
}

# --- Commands ---

cmd_get_device_id() {
  local executor_id="" event_date=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --executor-id) executor_id="$2"; shift 2 ;;
      --date) event_date="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
  done

  if [[ -z "$executor_id" || -z "$event_date" ]]; then
    echo "ERROR: --executor-id and --date are required" >&2
    exit 1
  fi

  local query
  query=$(render_template "$QUERIES_DIR/get_device_id.sql" \
    "EXECUTOR_ID=$executor_id" \
    "EVENT_DATE=$event_date")

  echo "=== Looking up appmetrica_device_id ===" >&2
  echo "Executor ID: $executor_id" >&2
  echo "Date: $event_date" >&2
  echo "" >&2

  "$YQL_CLI" run --query "$query" --clickhouse --clickhouse
}

cmd_get_mobile_logs() {
  local device_id="" event_date="" event_datetime="" api_key="3324463" event_name=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --device-id) device_id="$2"; shift 2 ;;
      --date) event_date="$2"; shift 2 ;;
      --datetime) event_datetime="$2"; shift 2 ;;
      --api-key) api_key="$2"; shift 2 ;;
      --event-name) event_name="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
  done

  if [[ -z "$device_id" || -z "$event_date" ]]; then
    echo "ERROR: --device-id and --date are required" >&2
    exit 1
  fi

  # Build datetime filter
  local datetime_filter=""
  if [[ -n "$event_datetime" ]]; then
    datetime_filter="and EventDateTime >= '$event_datetime'"
  fi

  local query
  query=$(render_template "$QUERIES_DIR/get_mobile_logs.sql" \
    "DEVICE_ID=$device_id" \
    "EVENT_DATE=$event_date" \
    "DATETIME_FILTER=$datetime_filter" \
    "API_KEY=$api_key")

  # Add event name filter if specified
  if [[ -n "$event_name" ]]; then
    query="${query/ORDER BY/and EventName like '$event_name'
ORDER BY}"
  fi

  echo "=== Fetching mobile logs ===" >&2
  echo "Device ID: $device_id" >&2
  echo "Date: $event_date" >&2
  [[ -n "$event_datetime" ]] && echo "After: $event_datetime" >&2
  [[ -n "$event_name" ]] && echo "Event filter: $event_name" >&2
  echo "API Key: $api_key" >&2
  echo "" >&2

  "$YQL_CLI" run --query "$query" --clickhouse --clickhouse
}

cmd_analyze_ticket() {
  local ticket="" executor_id="" event_date=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --ticket) ticket="$2"; shift 2 ;;
      --executor-id) executor_id="$2"; shift 2 ;;
      --date) event_date="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
  done

  if [[ -z "$ticket" || -z "$executor_id" || -z "$event_date" ]]; then
    echo "ERROR: --ticket, --executor-id, and --date are required" >&2
    exit 1
  fi

  echo "========================================" >&2
  echo "  Duty Ticket Analysis: $ticket" >&2
  echo "========================================" >&2
  echo "" >&2

  # Step 1: Show ticket
  echo "--- Step 1: Ticket Details ---" >&2
  "$TRACKER_CLI" show "$ticket" 2>&1 || echo "(Failed to fetch ticket, continuing...)" >&2
  echo "" >&2

  # Step 2: Get device ID
  echo "--- Step 2: Looking up device ID ---" >&2
  local device_result
  device_result=$(cmd_get_device_id --executor-id "$executor_id" --date "$event_date")
  echo "$device_result"
  echo "" >&2

  echo "Device ID lookup complete. Use get-mobile-logs with the device ID to fetch logs." >&2
}

# --- Main ---
if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

command="$1"
shift

case "$command" in
  get-device-id)    cmd_get_device_id "$@" ;;
  get-mobile-logs)  cmd_get_mobile_logs "$@" ;;
  analyze-ticket)   cmd_analyze_ticket "$@" ;;
  help|-h|--help)   usage ;;
  *)
    echo "Unknown command: $command" >&2
    usage
    exit 1
    ;;
esac
