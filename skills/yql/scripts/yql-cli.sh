#!/usr/bin/env bash
set -euo pipefail

# YQL CLI — lightweight wrapper over YQL REST API
# Execute queries, check status, retrieve results

BASE_URL="https://yql.yandex.net/api/v2"

# --- Auth ---
get_token() {
  if [[ -n "${YQL_TOKEN:-}" ]]; then
    echo "$YQL_TOKEN"
  elif [[ -n "${YQL_OAUTH_TOKEN:-}" ]]; then
    echo "$YQL_OAUTH_TOKEN"
  elif [[ -f "$HOME/.yql-token" ]]; then
    cat "$HOME/.yql-token"
  else
    echo "ERROR: No YQL token found." >&2
    echo "Set YQL_TOKEN env var or save token to ~/.yql-token" >&2
    echo "Get token: https://yql.yandex-team.ru/ → Settings" >&2
    exit 1
  fi
}

TOKEN=""
JSON_OUTPUT="false"
auth_header() {
  [[ -z "$TOKEN" ]] && TOKEN="$(get_token)"
  echo "Authorization: OAuth $TOKEN"
}

# --- API helpers ---
api_get() {
  local path="$1"
  curl -sf -H "$(auth_header)" -H "Content-Type: application/json" "${BASE_URL}${path}"
}

api_post() {
  local path="$1"
  local body="${2:-"{}"}"
  curl -sf -H "$(auth_header)" -H "Content-Type: application/json" -d "$body" "${BASE_URL}${path}"
}

# --- Helpers ---
wait_for_completion() {
  local op_id="$1"
  local max_wait="${2:-300}"  # default 5 min
  local elapsed=0
  local interval=3

  while [[ $elapsed -lt $max_wait ]]; do
    local status_resp
    status_resp=$(api_get "/operations/${op_id}")
    local status
    status=$(echo "$status_resp" | jq -r '.status // empty')

    case "$status" in
      COMPLETED)
        echo "COMPLETED" >&2
        return 0
        ;;
      ERROR|ABORTED)
        echo "Operation $status" >&2
        echo "$status_resp" | jq -r '.data.issues // .issues // empty' >&2
        return 1
        ;;
      *)
        echo "Status: $status (${elapsed}s elapsed)..." >&2
        sleep "$interval"
        elapsed=$((elapsed + interval))
        # increase interval gradually
        [[ $interval -lt 10 ]] && interval=$((interval + 2))
        ;;
    esac
  done

  echo "ERROR: Timeout after ${max_wait}s waiting for operation $op_id" >&2
  return 1
}

format_results() {
  local results_json="$1"
  echo "$results_json" | jq -r '
    if .data then
      .data[] |
      if .Write then
        .Write[]? |
        if .Type == "DISCARD" or .Type == null then empty
        else
          # Extract column names from Type structure: ["ListType", ["StructType", [[name, type], ...]]]
          (
            if (.Type | type) == "array" and (.Type[0] == "ListType") then
              [.Type[1][1][][] | select(type == "string")] as $all_strings |
              [.Type[1][1][] | .[0]] | join("\t")
            elif .Columns then
              .Columns | map(.Name) | join("\t")
            else
              empty
            end
          ),
          (.Data[]? | map(tostring) | join("\t"))
        end
      else empty end
    else
      .
    end
  ' 2>/dev/null || echo "$results_json" | jq '.'
}

# --- Commands ---

usage() {
  cat <<'USAGE'
YQL CLI — Execute YQL queries via REST API

Usage: yql-cli.sh <command> [options]

Commands:
  run         Execute query and wait for results (synchronous)
  submit      Submit query (asynchronous, returns operation ID)
  status      Check operation status
  results     Get operation results
  get-query   Get query text from existing operation
  abort       Abort running operation

Options for run/submit:
  --query TEXT         YQL query text (required, or use --file)
  --file PATH          Read query from file
  --cluster NAME       YT cluster (default: hahn)
  --clickhouse         Use ClickHouse syntax
  --title TEXT         Operation title
  --timeout SECONDS    Max wait time for run (default: 300)

Options for status/results/get-query/abort:
  --id OPERATION_ID    Operation ID (required)

Options for results:
  --format FORMAT      Output format: json (default), tsv, csv
  --raw                Output raw JSON response

Examples:
  yql-cli.sh run --query "SELECT 1+1"
  yql-cli.sh run --file query.sql --cluster arnold
  yql-cli.sh submit --query "SELECT * FROM t" --title "My query"
  yql-cli.sh status --id abc123
  yql-cli.sh results --id abc123
  yql-cli.sh get-query --id abc123
  yql-cli.sh abort --id abc123
USAGE
}

cmd_run() {
  local query="" file="" cluster="hahn" clickhouse=false title="" timeout=300

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --query) query="$2"; shift 2 ;;
      --file) file="$2"; shift 2 ;;
      --cluster) cluster="$2"; shift 2 ;;
      --clickhouse) clickhouse=true; shift ;;
      --title) title="$2"; shift 2 ;;
      --timeout) timeout="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
  done

  if [[ -n "$file" ]]; then
    query=$(cat "$file")
  fi

  if [[ -z "$query" ]]; then
    echo "ERROR: --query or --file required" >&2
    exit 1
  fi

  [[ -z "$title" ]] && title="YQL CLI query [YQL]"

  # Prepend USE cluster pragma if not already in query
  if ! echo "$query" | grep -qi '^\s*use\s'; then
    query="USE ${cluster};
${query}"
  fi

  local query_type="SQLv1"
  if $clickhouse; then
    query_type="CLICKHOUSE"
  fi

  local body
  body=$(jq -n \
    --arg content "$query" \
    --arg type "$query_type" \
    --arg title "$title" \
    '{
      content: $content,
      type: $type,
      action: "RUN",
      title: $title
    }')

  echo "Submitting query (type: $query_type)..." >&2
  local resp
  resp=$(api_post "/operations" "$body")

  local op_id
  op_id=$(echo "$resp" | jq -r '.id // empty')

  if [[ -z "$op_id" ]]; then
    echo "ERROR: Failed to submit query" >&2
    echo "$resp" | jq '.' >&2
    exit 1
  fi

  echo "Operation ID: $op_id" >&2
  echo "URL: https://yql.yandex-team.ru/Operations/$op_id" >&2

  wait_for_completion "$op_id" "$timeout" || exit 1

  # Get results
  local results
  results=$(api_get "/operations/${op_id}/results?filters=DATA")

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$results"
  else
    format_results "$results"
  fi
}

cmd_submit() {
  local query="" file="" cluster="hahn" clickhouse=false title=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --query) query="$2"; shift 2 ;;
      --file) file="$2"; shift 2 ;;
      --cluster) cluster="$2"; shift 2 ;;
      --clickhouse) clickhouse=true; shift ;;
      --title) title="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
  done

  if [[ -n "$file" ]]; then
    query=$(cat "$file")
  fi

  if [[ -z "$query" ]]; then
    echo "ERROR: --query or --file required" >&2
    exit 1
  fi

  [[ -z "$title" ]] && title="YQL CLI query [YQL]"

  # Prepend USE cluster pragma if not already in query
  if ! echo "$query" | grep -qi '^\s*use\s'; then
    query="USE ${cluster};
${query}"
  fi

  local query_type="SQLv1"
  if $clickhouse; then
    query_type="CLICKHOUSE"
  fi

  local body
  body=$(jq -n \
    --arg content "$query" \
    --arg type "$query_type" \
    --arg title "$title" \
    '{
      content: $content,
      type: $type,
      action: "RUN",
      title: $title
    }')

  local resp
  resp=$(api_post "/operations" "$body")

  local op_id
  op_id=$(echo "$resp" | jq -r '.id // empty')
  local status
  status=$(echo "$resp" | jq -r '.status // empty')

  if [[ -z "$op_id" ]]; then
    echo "ERROR: Failed to submit query" >&2
    echo "$resp" | jq '.' >&2
    exit 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$resp"
  else
    echo "Operation ID: $op_id"
    echo "Status: $status"
    echo "URL: https://yql.yandex-team.ru/Operations/$op_id"
  fi
}

cmd_status() {
  local op_id=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id) op_id="$2"; shift 2 ;;
      *) op_id="$1"; shift ;;
    esac
  done

  if [[ -z "$op_id" ]]; then
    echo "ERROR: --id required" >&2
    exit 1
  fi

  local resp
  resp=$(api_get "/operations/${op_id}")

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$resp"
  else
    echo "$resp" | jq '{id: .id, status: .status, title: .title, updatedAt: .updatedAt, issues: .data.issues}'
  fi
}

cmd_results() {
  local op_id="" raw=false

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id) op_id="$2"; shift 2 ;;
      --raw) raw=true; shift ;;
      *) op_id="$1"; shift ;;
    esac
  done

  if [[ -z "$op_id" ]]; then
    echo "ERROR: --id required" >&2
    exit 1
  fi

  local resp
  resp=$(api_get "/operations/${op_id}/results?filters=DATA")

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$resp"
  elif $raw; then
    echo "$resp" | jq '.'
  else
    format_results "$resp"
  fi
}

cmd_get_query() {
  local op_id=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id) op_id="$2"; shift 2 ;;
      *) op_id="$1"; shift ;;
    esac
  done

  if [[ -z "$op_id" ]]; then
    echo "ERROR: --id required" >&2
    exit 1
  fi

  local resp
  resp=$(api_get "/operations/${op_id}")

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$resp"
  else
    echo "$resp" | jq -r '.queryData.content // .content // "Query text not found"'
  fi
}

cmd_abort() {
  local op_id=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id) op_id="$2"; shift 2 ;;
      *) op_id="$1"; shift ;;
    esac
  done

  if [[ -z "$op_id" ]]; then
    echo "ERROR: --id required" >&2
    exit 1
  fi

  local resp
  resp=$(api_post "/operations/${op_id}" '{"action":"ABORT"}')

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$resp"
  else
    echo "$resp" | jq '{id: .id, status: .status}'
  fi
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
  run)        cmd_run "$@" ;;
  submit)     cmd_submit "$@" ;;
  status)     cmd_status "$@" ;;
  results)    cmd_results "$@" ;;
  get-query)  cmd_get_query "$@" ;;
  abort)      cmd_abort "$@" ;;
  help|-h|--help) usage ;;
  *)
    echo "Unknown command: $command" >&2
    usage
    exit 1
    ;;
esac
