#!/usr/bin/env bash
set -euo pipefail

# Monium CLI — query logs via Monium gRPC API using ya tool grpcurl
# Endpoint: query-prod.logs.yandex-team.ru:443

MONIUM_HOST="query-prod.logs.yandex-team.ru:443"
GRPCURL="ya tool grpcurl"

# --- Auth ---
get_token() {
  if [[ -n "${MONIUM_TOKEN:-}" ]]; then
    echo "$MONIUM_TOKEN"
  elif [[ -n "${OAUTH_TOKEN:-}" ]]; then
    echo "$OAUTH_TOKEN"
  elif [[ -f "$HOME/.mcp_store/oauth_token" ]]; then
    cat "$HOME/.mcp_store/oauth_token"
  elif [[ -f "$HOME/.yql-token" ]]; then
    cat "$HOME/.yql-token"
  else
    echo "ERROR: No token found." >&2
    echo "Set MONIUM_TOKEN env var or save token to ~/.mcp_store/oauth_token" >&2
    exit 1
  fi
}

TOKEN=""
JSON_OUTPUT="false"
get_auth_token() {
  [[ -z "$TOKEN" ]] && TOKEN="$(get_token)"
  echo "$TOKEN"
}

# --- Commands ---

usage() {
  cat <<'USAGE'
Monium CLI — query logs via Monium gRPC API

Usage: monium-cli.sh <command> [options]

Commands:
  search          Search logs by selector query
  services        List available services (via reflection)

Options for search:
  --project NAME       Project name (default: taxi)
  --service NAME       Service name (required unless --query given)
  --query SELECTOR     Full selector query (overrides --project/--service)
  --meta-type PATH     Filter by endpoint/handler path (label meta_type)
  --meta KEY=VALUE     Filter results by meta/label field value (repeatable, e.g. --meta meta_driver_id=UUID)
  --start DATETIME     Start time, ISO 8601 or "YYYY-MM-DD HH:MM:SS" (required)
  --end DATETIME       End time (default: start + 10 min)
  --duration SECONDS   Duration from start (alternative to --end, default: 600)
  --limit N            Max log entries (default: 100)
  --trace TRACE_ID     Search by trace ID (overrides other selector options)
  --filter TEXT        Filter message by substring (grep on results)
  --level LEVEL        Filter by log level: INFO, WARN, ERROR, DEBUG
  --raw                Output raw JSON (default: formatted)

Selector query language:
  {project="taxi", service="driver-money"}
  {project="taxi", service="driver-money", level="ERROR"}
  {project="taxi", service="driver-money"} message=*"instant_payout"
  {project="taxi", service="driver-money"} meta.contractor_profile_id="UUID"

Common meta fields for user IDs (vary by service):
  contractor_profile_id, driver_profile_id, contractor_id,
  park_id, order_id, request_id

Examples:
  monium-cli.sh search --service driver-money --start "2026-02-24 13:40:00" --limit 10
  monium-cli.sh search --service driver-money --meta-type /internal/driver-money/v1/contractor/balance --start "2026-02-24 13:40:00"
  monium-cli.sh search --service driver-money --meta-type /internal/driver-money/v1/contractor/balance --meta contractor_profile_id=UUID --start "2026-02-24 13:40:00"
  monium-cli.sh search --service driver-money --start "2026-02-24 13:40:00" --level ERROR --meta park_id=UUID
  monium-cli.sh search --service driver-money --start "2026-02-24 13:40:00" --filter "instant_payout"
USAGE
}

to_iso8601() {
  local dt="$1"
  # If already has T and Z, pass through
  if [[ "$dt" == *"T"*"Z" ]]; then
    echo "$dt"
    return
  fi
  # Convert "YYYY-MM-DD HH:MM:SS" to ISO 8601
  if [[ "$dt" == *" "* ]]; then
    echo "${dt/ /T}Z"
  else
    # Just date, add time
    echo "${dt}T00:00:00Z"
  fi
}

add_seconds() {
  local iso_dt="$1"
  local seconds="$2"
  # Use python for reliable date math
  python3 -c "
from datetime import datetime, timedelta, timezone
dt = datetime.fromisoformat('${iso_dt}'.replace('Z', '+00:00'))
dt += timedelta(seconds=${seconds})
print(dt.strftime('%Y-%m-%dT%H:%M:%SZ'))
"
}

format_logs() {
  local filter="${1:-}"
  local level_filter="${2:-}"

  jq -r '
    .logs[]? |
    "\(.time)\t\(.level)\t\(.host // "")\t\(.message)\t" +
    ([.labels[]? | "\(.name)=\(.value)"] | join(" ")) + "\t" +
    ([.meta[]? | select(.name == "uri" or .name == "useragent" or .name == "request_id" or .name == "response_code") | "\(.name)=\(.value)"] | join(" "))
  ' | if [[ -n "$filter" ]]; then grep -i "$filter"; else cat; fi \
    | if [[ -n "$level_filter" ]]; then grep "${level_filter}"; else cat; fi
}

cmd_search() {
  local project="taxi" service="" query="" start="" end="" duration=600 limit=100 filter="" level="" raw=false
  local meta_type="" trace_id=""
  local -a meta_filters=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --project) project="$2"; shift 2 ;;
      --service) service="$2"; shift 2 ;;
      --query) query="$2"; shift 2 ;;
      --trace) trace_id="$2"; shift 2 ;;
      --meta-type) meta_type="$2"; shift 2 ;;
      --meta) meta_filters+=("$2"); shift 2 ;;
      --start) start="$2"; shift 2 ;;
      --end) end="$2"; shift 2 ;;
      --duration) duration="$2"; shift 2 ;;
      --limit) limit="$2"; shift 2 ;;
      --filter) filter="$2"; shift 2 ;;
      --level) level="$2"; shift 2 ;;
      --raw) raw=true; shift ;;
      *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
  done

  if [[ -z "$start" ]]; then
    echo "ERROR: --start is required" >&2
    exit 1
  fi

  if [[ -z "$query" && -z "$service" && -z "$trace_id" ]]; then
    echo "ERROR: --service, --query, or --trace is required" >&2
    exit 1
  fi

  # For trace-only search, service is not required
  if [[ -n "$trace_id" && -z "$service" && -z "$query" ]]; then
    query="{project=\"${project}\", trace.id = \"${trace_id}\"}"
    trace_id=""  # already included in query
  fi

  local start_iso
  start_iso=$(to_iso8601 "$start")

  local end_iso
  if [[ -n "$end" ]]; then
    end_iso=$(to_iso8601 "$end")
  else
    end_iso=$(add_seconds "$start_iso" "$duration")
  fi

  # Build selector query
  if [[ -z "$query" ]]; then
    # Build labels part
    local labels="project=\"${project}\""
    [[ -n "$service" ]] && labels="${labels}, service=\"${service}\""
    [[ -n "$level" ]] && labels="${labels}, level=\"${level}\""
    [[ -n "$meta_type" ]] && labels="${labels}, meta_type=\"${meta_type}\""

    # Add meta filters as meta.key = "value" inside selector
    for mf in "${meta_filters[@]+"${meta_filters[@]}"}"; do
      local key="${mf%%=*}"
      local value="${mf#*=}"
      labels="${labels}, meta.${key} = \"${value}\""
    done

    query="{${labels}}"
  fi

  # Append trace filter inside selector if provided
  if [[ -n "$trace_id" ]]; then
    # trace.id goes inside the selector braces: {project="taxi", trace.id="..."}
    query="${query%\}}, trace.id = \"${trace_id}\"}"
  fi

  local request_body
  request_body=$(jq -n \
    --arg query "$query" \
    --arg start "$start_iso" \
    --arg end "$end_iso" \
    --argjson limit "$limit" \
    '{
      queries: [$query],
      start: $start,
      end: $end,
      limit: $limit
    }')

  echo "Searching logs: $query" >&2
  echo "Time: $start_iso → $end_iso (limit: $limit)" >&2

  local auth_token
  auth_token=$(get_auth_token)

  local result
  result=$($GRPCURL -H "Authorization: Bearer $auth_token" \
    -d "$request_body" \
    "$MONIUM_HOST" \
    monium.logs.query.v1.Query/SearchLogs 2>&1)

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result"
    return
  fi

  if $raw; then
    echo "$result" | jq '.'
  else
    local count
    count=$(echo "$result" | jq '[.logs[]?] | length' 2>/dev/null || echo 0)
    echo "Found $count log entries" >&2

    if [[ "$count" == "0" ]]; then
      echo "(no logs found)"
    else
      echo "$result" | format_logs "$filter" "$level"
    fi
  fi
}

cmd_services() {
  local auth_token
  auth_token=$(get_auth_token)
  $GRPCURL -H "Authorization: Bearer $auth_token" "$MONIUM_HOST" list
}

# --- Main ---
if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

# Parse global flags
args=()
for arg in "$@"; do
  [[ "$arg" == "--json" ]] && JSON_OUTPUT="true" || args+=("$arg")
done
set -- "${args[@]+"${args[@]}"}"

command="$1"
shift

case "$command" in
  search)     cmd_search "$@" ;;
  services)   cmd_services "$@" ;;
  help|-h|--help) usage ;;
  *)
    echo "Unknown command: $command" >&2
    usage
    exit 1
    ;;
esac
