#!/usr/bin/env bash
set -euo pipefail

# Sandbox CLI — wrapper over Sandbox REST API + log analysis
# Handles: task search, log fetching, error parsing, S3 artifacts

SANDBOX_API="https://sandbox.yandex-team.ru/api/v1.0"
SANDBOX_PROXY="https://proxy.sandbox.yandex-team.ru"

# --- Auth ---
get_ci_token() {
  if [[ -n "${CI_OAUTH_TOKEN:-}" ]]; then
    echo "$CI_OAUTH_TOKEN"
  elif [[ -f "$HOME/.ci/token" ]]; then
    cat "$HOME/.ci/token" | tr -d '[:space:]'
  else
    echo "ERROR: CI token required. Save to ~/.ci/token or set CI_OAUTH_TOKEN" >&2
    echo "Get token: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=92335dd01cb64811bd913f7164f30594" >&2
    return 1
  fi
}

CI_TOKEN=""
JSON_OUTPUT="false"

ensure_token() {
  [[ -z "$CI_TOKEN" ]] && CI_TOKEN="$(get_ci_token)"
}

cli_error() {
  local code="$1" msg="$2" suggestion="${3:-}"
  if [[ "$JSON_OUTPUT" == "true" ]]; then
    jq -n --arg c "$code" --arg m "$msg" --arg s "$suggestion" \
      '{status:"error", code:$c, message:$m} | if $s != "" then . + {suggestion:$s} else . end' >&2
  else
    echo "ERROR: $msg" >&2
    [[ -n "$suggestion" ]] && echo "  Hint: $suggestion" >&2
  fi
  return 1
}

# --- API helpers ---
sb_get() {
  local path="$1"
  ensure_token
  curl -sf --max-time 30 -H "Authorization: OAuth $CI_TOKEN" "${SANDBOX_API}${path}"
}

sb_proxy_get() {
  local url="$1"
  local range="${2:-}"
  ensure_token
  if [[ -n "$range" ]]; then
    curl -sf --max-time 60 -H "Authorization: OAuth $CI_TOKEN" -r "$range" "$url" 2>/dev/null
  else
    curl -sf --max-time 60 -H "Authorization: OAuth $CI_TOKEN" "$url" 2>/dev/null
  fi
}

# --- Get TASK_LOGS resource ID for a task ---
get_logs_resource_id() {
  local task_id="$1"
  local resources
  resources=$(sb_get "/resource?task_id=${task_id}&type=TASK_LOGS&limit=1")
  echo "$resources" | jq -r '.items[0].id // empty'
}

# --- Get execution.log content (last N bytes) ---
get_execution_log() {
  local logs_id="$1"
  local bytes="${2:-2000000}"
  sb_proxy_get "${SANDBOX_PROXY}/${logs_id}/execution.log" "-${bytes}"
}

# --- Commands ---

cmd_tasks() {
  local pr_id="$1"
  local action_filter="${2:-}"

  ensure_token

  local search_tags="CI"
  local all_tags=""
  if [[ -n "$action_filter" ]]; then
    local action_tag="ACTION:$(echo "$action_filter" | tr '[:lower:]' '[:upper:]')"
    search_tags="${search_tags},${action_tag}"
    all_tags="&all_tags=true"
  fi

  local http_code
  local tmpfile="/tmp/sandbox_tasks_$$.json"
  http_code=$(curl -sf -o "$tmpfile" -w "%{http_code}" --max-time 30 \
    -H "Authorization: OAuth $CI_TOKEN" \
    "${SANDBOX_API}/task?limit=30&order=-id&tags=${search_tags}&hints=PR%3A${pr_id}${all_tags}" 2>/dev/null) || http_code="000"

  if [[ "$http_code" != "200" ]] || [[ ! -s "$tmpfile" ]]; then
    rm -f "$tmpfile"
    echo "ERROR: Sandbox API unavailable (HTTP $http_code)" >&2
    return 1
  fi

  local filtered
  filtered=$(jq '.items // []' "$tmpfile")
  rm -f "$tmpfile"

  local total
  total=$(echo "$filtered" | jq 'length')

  if [[ "$total" == "0" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then echo "[]"; else echo "No Sandbox tasks found for PR $pr_id."; fi
    return
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$filtered" | jq '[.[] | {id, status, type, tags}]'
    return
  fi

  echo "$filtered" | jq -r '.[] |
    (if .status == "SUCCESS" then "✅"
     elif .status == "FAILURE" then "❌"
     elif .status == "EXCEPTION" then "💥"
     elif .status == "EXECUTING" then "⏳"
     elif .status == "ENQUEUED" or .status == "ASSIGNED" then "🔄"
     else "❓" end) + " " +
    (.status | . + " " + (" " * (10 - length))) +
    ((.tags // []) | map(select(startswith("JOB-ID:"))) | .[0] // "unknown" | ltrimstr("JOB-ID:")) +
    " (task " + (.id | tostring) + ")"'
}

cmd_task_info() {
  local task_id="$1"

  local task
  task=$(sb_get "/task/${task_id}")

  if [[ -z "$task" ]]; then
    cli_error "not_found" "Task $task_id not found" "Check task ID"
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$task" | jq '{id, status, type, tags}'
    return
  fi

  local task_status task_type job_id action_tag
  task_status=$(echo "$task" | jq -r '.status')
  task_type=$(echo "$task" | jq -r '.type')
  job_id=$(echo "$task" | jq -r '[.tags[] | select(startswith("JOB-ID:"))] | .[0] // "unknown" | ltrimstr("JOB-ID:")')
  action_tag=$(echo "$task" | jq -r '[.tags[] | select(startswith("ACTION:"))] | .[0] // "unknown" | ltrimstr("ACTION:")')

  echo "=== Task $task_id ==="
  echo "Job:    $job_id"
  echo "Action: $action_tag"
  echo "Type:   $task_type"
  echo "Status: $task_status"

  local logs_id
  logs_id=$(get_logs_resource_id "$task_id")
  if [[ -n "$logs_id" ]]; then
    echo "Logs:   ${SANDBOX_PROXY}/${logs_id}/"
  else
    echo "Logs:   (no TASK_LOGS resource)"
  fi
}

cmd_log() {
  local task_id="$1"
  local log_file="${2:-execution_error.log}"

  cmd_task_info "$task_id"
  echo ""

  local logs_id
  logs_id=$(get_logs_resource_id "$task_id")

  if [[ -z "$logs_id" ]]; then
    echo "No TASK_LOGS resource found."
    return
  fi

  if [[ "$log_file" == "execution_error.log" ]]; then
    echo "=== Errors (execution.log) ==="
    sb_proxy_get "${SANDBOX_PROXY}/${logs_id}/execution.log" "-500000" \
      | grep -iE '(❌|error:|Error:|FAILED|BUILD FAILED|ARCHIVE FAILED|Compilation failed|exit code [1-9])' \
      | grep -viE '(warning:|note:|Disabling previews|TREAT_MISSING|error_name)' \
      | tail -30

    echo ""
    echo "=== Last 30 lines (execution_error.log) ==="
    sb_proxy_get "${SANDBOX_PROXY}/${logs_id}/execution_error.log" \
      | grep -vE '(^$|Disabling previews|deprecated.*API_DEPRECATED)' \
      | tail -30
  else
    echo "=== ${log_file} (last 100 lines) ==="
    sb_proxy_get "${SANDBOX_PROXY}/${logs_id}/${log_file}" | tail -100
  fi
}

cmd_errors() {
  local task_id="$1"

  cmd_task_info "$task_id"
  echo ""

  local logs_id
  logs_id=$(get_logs_resource_id "$task_id")

  if [[ -z "$logs_id" ]]; then
    echo "No TASK_LOGS resource found."
    return
  fi

  local exec_log
  exec_log=$(get_execution_log "$logs_id" "3000000")

  if [[ -z "$exec_log" ]]; then
    echo "Could not fetch execution.log"
    return
  fi

  # --- 1. Test errors block ---
  local test_errors
  test_errors=$(echo "$exec_log" | sed -n '/Test errors with paths list:/,/Some tests failed/p' 2>/dev/null || true)
  if [[ -n "$test_errors" ]]; then
    echo "=== Test Failures ==="
    echo "$test_errors" | grep -E '(Test:|Path to work dir:)' | head -20
    echo ""
  fi

  # --- 2. Dart format failures ---
  local format_block
  format_block=$(echo "$exec_log" | sed -n '/dart format.*--set-exit-if-changed\|dart format -o none/,/blockClosed.*format/p' 2>/dev/null || true)
  if echo "$format_block" | grep -q 'format end with error' 2>/dev/null; then
    echo "=== Dart Format Failures ==="
    local changed_files
    changed_files=$(echo "$format_block" | grep -E '^\S*\s*Changed ' | sed 's/^.*Changed /  /')
    local summary_line
    summary_line=$(echo "$format_block" | grep 'Formatted .* files .* changed' | sed 's/^[0-9-]* [0-9:]* //')
    if [[ -n "$changed_files" ]]; then
      echo "Files that need formatting:"
      echo "$changed_files"
    fi
    if [[ -n "$summary_line" ]]; then
      echo "$summary_line"
    fi
    echo ""
  fi

  # --- 3. Dart analyzer errors ---
  local analyzer_block
  analyzer_block=$(echo "$exec_log" | sed -n '/dart analyze\|flutter analyze/,/blockClosed.*analyz/p' 2>/dev/null || true)
  if echo "$analyzer_block" | grep -q 'end with error' 2>/dev/null; then
    echo "=== Dart Analyzer Errors ==="
    echo "$analyzer_block" | grep -E '(error •|error -|error:)' | head -20
    echo ""
  fi

  # --- 4. Build failures ---
  local build_errors
  build_errors=$(echo "$exec_log" | grep -iE '(BUILD FAILED|ARCHIVE FAILED|Compilation failed|Error:.*is imported from both)' 2>/dev/null || true)
  if [[ -n "$build_errors" ]]; then
    echo "=== Build Errors ==="
    echo "$build_errors" | tail -20
    echo ""
  fi

  # --- 5. Flutter test failures (individual test errors) ---
  local test_fail_lines
  test_fail_lines=$(echo "$exec_log" | grep -E '(Expected:|Actual:|Which:|══.*Exception|Test failed)' 2>/dev/null || true)
  if [[ -n "$test_fail_lines" ]]; then
    echo "=== Unit Test Errors ==="
    echo "$test_fail_lines" | tail -30
    echo ""
  fi

  # --- 6. Generic error lines (fallback) ---
  # If nothing above matched, show generic errors
  if [[ -z "$test_errors" && -z "$format_block" && -z "$build_errors" && -z "$test_fail_lines" ]]; then
    echo "=== Generic Errors (execution.log) ==="
    echo "$exec_log" \
      | grep -iE '(error:|FAILED|exit code [1-9])' \
      | grep -viE '(warning:|note:|Disabling previews|TREAT_MISSING|error_name|cut_execution_log)' \
      | tail -30
    echo ""
  fi

  # --- 7. execution_error.log (always show) ---
  echo "=== execution_error.log (last 20 lines) ==="
  sb_proxy_get "${SANDBOX_PROXY}/${logs_id}/execution_error.log" \
    | grep -vE '(^$|Disabling previews|deprecated.*API_DEPRECATED)' \
    | tail -20
}

cmd_artifact() {
  local task_id="$1"
  local artifact_type="${2:-TASK_LOGS}"
  local file_path="${3:-}"

  ensure_token

  local resources
  resources=$(sb_get "/resource?task_id=${task_id}&type=${artifact_type}&limit=1")
  local resource_id
  resource_id=$(echo "$resources" | jq -r '.items[0].id // empty')

  if [[ -z "$resource_id" ]]; then
    echo "ERROR: No ${artifact_type} resource found for task $task_id" >&2
    return 1
  fi

  echo "Resource: ${SANDBOX_PROXY}/${resource_id}/"

  if [[ -n "$file_path" ]]; then
    echo ""
    echo "=== ${file_path} ==="
    sb_proxy_get "${SANDBOX_PROXY}/${resource_id}/${file_path}"
  else
    # List available files
    echo ""
    echo "Fetching directory listing..."
    local listing
    listing=$(sb_proxy_get "${SANDBOX_PROXY}/${resource_id}/" 2>/dev/null || true)
    if [[ -n "$listing" ]]; then
      echo "$listing" | grep -oE 'href="[^"]*"' | sed 's/href="//;s/"//' | grep -vE '^\.\.$|^/$' | head -30
    fi
  fi
}

cmd_search_log() {
  local task_id="$1"
  local pattern="${2:-}"
  local context="${3:-3}"

  if [[ -z "$pattern" ]]; then
    echo "ERROR: PATTERN is required" >&2
    echo "Usage: sandbox-cli.sh search-log TASK_ID PATTERN [CONTEXT_LINES]" >&2
    return 1
  fi

  local logs_id
  logs_id=$(get_logs_resource_id "$task_id")

  if [[ -z "$logs_id" ]]; then
    echo "No TASK_LOGS resource found for task $task_id."
    return 1
  fi

  echo "=== Searching execution.log for: $pattern ==="
  local exec_log
  exec_log=$(get_execution_log "$logs_id" "5000000")

  if [[ -z "$exec_log" ]]; then
    echo "Could not fetch execution.log"
    return 1
  fi

  local results
  results=$(echo "$exec_log" | grep -iE -A"$context" -B"$context" "$pattern" 2>/dev/null || true)

  if [[ -z "$results" ]]; then
    echo "No matches found."
  else
    echo "$results" | head -100
  fi
}

cmd_failed() {
  local pr_id="$1"

  ensure_token

  # Find all failed tasks for this PR
  local tmpfile="/tmp/sandbox_failed_$$.json"
  local http_code
  http_code=$(curl -sf -o "$tmpfile" -w "%{http_code}" --max-time 30 \
    -H "Authorization: OAuth $CI_TOKEN" \
    "${SANDBOX_API}/task?limit=30&order=-id&tags=CI&hints=PR%3A${pr_id}&status=FAILURE" 2>/dev/null) || http_code="000"

  if [[ "$http_code" != "200" ]] || [[ ! -s "$tmpfile" ]]; then
    rm -f "$tmpfile"
    echo "ERROR: Sandbox API unavailable (HTTP $http_code)" >&2
    return 1
  fi

  local items
  items=$(jq '.items // []' "$tmpfile")
  rm -f "$tmpfile"

  local total
  total=$(echo "$items" | jq 'length')

  if [[ "$total" == "0" ]]; then
    echo "No failed tasks for PR $pr_id."
    return
  fi

  echo "=== Failed tasks for PR $pr_id ==="
  echo ""

  # For each failed task, run errors analysis
  local task_ids
  task_ids=$(echo "$items" | jq -r '.[].id')

  for tid in $task_ids; do
    local job_id
    job_id=$(echo "$items" | jq -r --argjson id "$tid" '.[] | select(.id == $id) | [.tags[] | select(startswith("JOB-ID:"))] | .[0] // "unknown" | ltrimstr("JOB-ID:")')

    # Skip COMBINING-TEST-ERROR-LOGS — it's a meta-task
    if [[ "$job_id" == *"COMBINING"* ]]; then
      continue
    fi

    cmd_errors "$tid"
    echo "---"
    echo ""
  done
}

# --- Main ---
usage() {
  cat <<'EOF'
Usage: sandbox-cli.sh [--json] <command> [args]

Commands:
  tasks PR_ID [ACTION_FILTER]        List Sandbox tasks for a PR
  task-info TASK_ID                  Task metadata (status, job, action)
  log TASK_ID [LOG_FILE]             Task logs (default: execution_error.log)
  errors TASK_ID                     Smart error analysis (tests, format, build)
  failed PR_ID                       All failed tasks + error analysis
  search-log TASK_ID PATTERN [CTX]   Grep execution.log
  artifact TASK_ID [TYPE] [FILE]     Access artifacts

Global flags:
  --json    Structured JSON output

Auth: CI_OAUTH_TOKEN env var or ~/.ci/token
Run 'help <command>' for detailed usage.
EOF
}

cmd_help_detail() {
  local cmd="$1"
  case "$cmd" in
    tasks) cat <<'EOF'
tasks PR_ID [ACTION_FILTER] [--json]
  List Sandbox tasks for a PR. ACTION_FILTER: action ID to filter by.
  Example: sandbox-cli.sh tasks 12345
  Example: sandbox-cli.sh tasks 12345 "Custom (testing)"
EOF
    ;;
    errors) cat <<'EOF'
errors TASK_ID [--json]
  Smart error analysis — parses execution.log for:
  - Test failures (test names + paths)
  - Dart format/analyzer errors
  - Build errors (compilation, archive)
  Example: sandbox-cli.sh errors 1234567890
EOF
    ;;
    *) echo "No detailed help for '$cmd'. Run 'sandbox-cli.sh help' for command list." ;;
  esac
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

# Parse global flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) JSON_OUTPUT="true"; shift ;;
    *) break ;;
  esac
done

command="${1:-help}"
shift || true

# Strip --json from remaining args
args=()
for arg in "$@"; do
  [[ "$arg" == "--json" ]] && JSON_OUTPUT="true" || args+=("$arg")
done
set -- "${args[@]+"${args[@]}"}"

case "$command" in
  tasks)      cmd_tasks "$@" ;;
  task-info)  cmd_task_info "$@" ;;
  log)        cmd_log "$@" ;;
  errors)     cmd_errors "$@" ;;
  failed)     cmd_failed "$@" ;;
  search-log) cmd_search_log "$@" ;;
  artifact)   cmd_artifact "$@" ;;
  help|--help|-h)
    if [[ $# -gt 0 ]]; then cmd_help_detail "$1"; else usage; fi ;;
  *)
    echo "Unknown command: $command" >&2
    usage
    exit 1
    ;;
esac
