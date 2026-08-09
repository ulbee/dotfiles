#!/usr/bin/env bash
set -euo pipefail

# Arcanum CLI — lightweight wrapper over Arcanum REST API
# Replaces ~37 Arcanum MCP tools with a single Bash script
# Pattern: same as tracker-cli.sh

BASE_URL="https://arcanum.yandex.net/api"
ARCADIA_ROOT="$HOME/arcadia"

# --- Auth ---
get_token() {
  if [[ -n "${ARC_OAUTH_TOKEN:-}" ]]; then
    echo "$ARC_OAUTH_TOKEN"
  elif [[ -f "$HOME/.arc/token" ]]; then
    cat "$HOME/.arc/token"
  else
    # Fallback: ask arc itself for the token
    local arc_token
    arc_token=$(cd "$ARCADIA_ROOT" && arc token show 2>/dev/null) || true
    if [[ -n "$arc_token" ]]; then
      echo "$arc_token"
    else
      echo "ERROR: No ARC token found." >&2
      echo "Set ARC_OAUTH_TOKEN, save to ~/.arc/token, or ensure 'arc token show' works" >&2
      exit 1
    fi
  fi
}

TOKEN=""
auth_header() {
  [[ -z "$TOKEN" ]] && TOKEN="$(get_token)"
  echo "Authorization: OAuth $TOKEN"
}

# --- API helpers ---
# All Arcanum API responses wrap payload in {"data": ...}
api_get() {
  local path="$1"
  curl -sf -H "$(auth_header)" -H "Content-Type: application/json" "${BASE_URL}${path}" | jq '.data'
}

api_post() {
  local path="$1"
  local body="${2:-"{}"}"
  curl -sf -H "$(auth_header)" -H "Content-Type: application/json" -d "$body" "${BASE_URL}${path}" | jq '.data'
}

api_patch() {
  local path="$1"
  local body="${2:-"{}"}"
  curl -sf -X PATCH -H "$(auth_header)" -H "Content-Type: application/json" -d "$body" "${BASE_URL}${path}" | jq '.data'
}

api_delete() {
  local path="$1"
  curl -sf -X DELETE -H "$(auth_header)" -H "Content-Type: application/json" "${BASE_URL}${path}"
}

api_patch_no_body() {
  local path="$1"
  curl -sf -X PATCH -H "$(auth_header)" -H "Content-Type: application/json" "${BASE_URL}${path}"
}

# --- Helpers ---

# Get active diff info for a PR: returns JSON with base, merge commit hashes and diff_set id
get_active_diff() {
  local pr_id="$1"
  local diff_info
  diff_info=$(api_get "/v1/pull-requests/${pr_id}/active-diff?fields=commit_ids(base,merge),id")
  if [[ -z "$diff_info" || "$diff_info" == "null" ]]; then
    echo "ERROR: Could not get active diff for PR $pr_id" >&2
    return 1
  fi
  echo "$diff_info"
}

# --- Commands ---

cmd_pr_status() {
  local pr_id="$1"
  local meta
  meta=$(api_get "/v1/pull-requests/${pr_id}?fields=id,summary,status,author(login),vcs(from_branch,to_branch),created_at,updated_at,merged_at")
  if [[ -z "$meta" || "$meta" == "null" ]]; then
    echo "ERROR: PR $pr_id not found" >&2
    return 1
  fi
  echo "$meta" | jq -r '"PR #\(.id): \(.status)\nSummary: \(.summary)\nAuthor:  \(.author)\nBranch:  \(.vcs.from_branch) → \(.vcs.to_branch)\nCreated: \(.created_at // "—")\nUpdated: \(.updated_at // "—")\nMerged:  \(.merged_at // "—")"'
}

cmd_pr_data() {
  local pr_id="$1"

  echo "=== PR Metadata ==="
  local meta
  meta=$(api_get "/v2/pull-requests/${pr_id}?fields=id,url,author(login,name),summary,description,status,vcs(from_branch,to_branch),approvers(login),checks(type,status)")
  if [[ -z "$meta" || "$meta" == "null" ]]; then
    echo "ERROR: PR $pr_id not found" >&2
    return 1
  fi
  echo "$meta" | jq '.'

  echo ""
  echo "=== Comments ==="
  # PR-level endpoint returns ALL comments (PR + inline) with anchor info
  local comments
  comments=$(api_get "/v2/public/pull-request/${pr_id}/comment?fields=id,author(name),content,is_draft,issue_status,created_at,anchor(destination_path,line,side)")
  if [[ -z "$comments" || "$comments" == "null" || "$comments" == "[]" ]]; then
    echo "No comments."
  else
    echo "$comments" | jq '[.[] | {
      id: .id,
      author: .author.name,
      content: .content,
      issue_status: .issue_status,
      file: (.anchor.destination_path // null),
      line: (.anchor.line // null),
      side: (.anchor.side // null),
      created: .created_at
    }]'
  fi
}

cmd_changed_files() {
  local pr_id="$1"

  local diff_info
  diff_info=$(get_active_diff "$pr_id")
  local diff_id
  diff_id=$(echo "$diff_info" | jq -r '.id')

  local changelist
  changelist=$(api_get "/v2/public/diff/${diff_id}/changelist?fields=path,change_type")

  if [[ -z "$changelist" || "$changelist" == "null" || "$changelist" == "[]" ]]; then
    echo "No changed files."
    return
  fi

  echo "$changelist" | jq -r '.[] | "\(.change_type // "M")\t\(.path)"'
}

cmd_file_diff() {
  local pr_id="$1"
  local file_path="$2"

  local diff_info
  diff_info=$(get_active_diff "$pr_id")
  local base
  base=$(echo "$diff_info" | jq -r '.commit_ids.base')
  local merge
  merge=$(echo "$diff_info" | jq -r '.commit_ids.merge')

  # Use local arc to get the diff
  cd "$ARCADIA_ROOT"
  local diff_text
  diff_text=$(arc diff "$base" "$merge" -- "$file_path")

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    jq -n --arg d "$diff_text" '{"diff": $d}'
  else
    echo "$diff_text"
  fi
}

cmd_file_content() {
  local pr_id="$1"
  local file_path="$2"

  local diff_info
  diff_info=$(get_active_diff "$pr_id")
  local merge
  merge=$(echo "$diff_info" | jq -r '.commit_ids.merge')

  # Use local arc to show file at merge commit
  cd "$ARCADIA_ROOT"
  local file_text
  file_text=$(arc show "${merge}:${file_path}")

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    jq -n --arg c "$file_text" '{"content": $c}'
  else
    echo "$file_text"
  fi
}

cmd_post_comment() {
  local pr_id="$1"
  shift

  local content="" draft="false" issue_status="" file_path="" line="" lines="" side="new"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --content)      content="$2"; shift 2 ;;
      --draft)        draft="$2"; shift 2 ;;
      --issue-status) issue_status="$2"; shift 2 ;;
      --file)         file_path="$2"; shift 2 ;;
      --line)         line="$2"; shift 2 ;;
      --lines)        lines="$2"; shift 2 ;;
      --side)         side="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  if [[ -z "$content" ]]; then
    echo "ERROR: --content is required" >&2
    return 1
  fi

  # Inline comment (file specified) → V2 Public API: POST /diff/{diff_id}/comment
  if [[ -n "$file_path" ]]; then
    local diff_info
    diff_info=$(get_active_diff "$pr_id")
    local diff_id
    diff_id=$(echo "$diff_info" | jq -r '.id')

    # Get entry_id via V2 changelist
    local entry_id
    entry_id=$(api_get "/v2/public/diff/${diff_id}/changelist?fields=path,entry_id" \
      | jq -r --arg f "$file_path" '.[] | select(.path == $f) | .entry_id')

    if [[ -z "$entry_id" || "$entry_id" == "null" ]]; then
      echo "ERROR: File '$file_path' not found in PR diff" >&2
      return 1
    fi

    local body
    body=$(jq -n \
      --arg eid "$entry_id" \
      --arg c "$content" \
      --argjson is_draft "$draft" \
      --arg s "$side" \
      '{entry_id: $eid, content: $c, is_draft: $is_draft, side: $s}')

    if [[ -n "$line" ]]; then
      body=$(echo "$body" | jq --argjson l "$line" '. + {line: $l}')
    fi
    if [[ -n "$lines" ]]; then
      body=$(echo "$body" | jq --argjson l "$lines" '. + {size: $l}')
    else
      body=$(echo "$body" | jq '. + {size: 1}')
    fi
    if [[ -n "$issue_status" ]]; then
      # V2 API: is_issue=true creates an open issue
      body=$(echo "$body" | jq '. + {is_issue: true}')
    fi

    local result
    result=$(api_post "/v2/public/diff/${diff_id}/comment?fields=id,content,anchor(line,side,destination_path),is_draft,issue_status" "$body")

    if [[ -z "$result" || "$result" == "null" ]]; then
      echo "ERROR: Failed to post inline comment" >&2
      return 1
    fi

    echo "$result" | jq '{id: .id, status: "posted", issue_status: .issue_status, file: .anchor.destination_path, line: .anchor.line}'
    return 0
  fi

  # PR-level comment → V2 Public API: POST /pull-request/{pr_id}/comment
  local body
  body=$(jq -n --arg c "$content" --argjson d "$draft" '{content: $c, is_draft: $d}')

  if [[ -n "$issue_status" ]]; then
    body=$(echo "$body" | jq '. + {is_issue: true}')
  fi

  local result
  result=$(api_post "/v2/public/pull-request/${pr_id}/comment?fields=id,content,is_draft,issue_status" "$body")

  if [[ -z "$result" || "$result" == "null" ]]; then
    echo "ERROR: Failed to post comment" >&2
    return 1
  fi

  echo "$result" | jq '{id: .id, status: "posted", issue_status: .issue_status}'
}

cmd_reply() {
  local comment_id="$1"
  shift

  local content="" draft="false" issue_status=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --content)      content="$2"; shift 2 ;;
      --draft)        draft="$2"; shift 2 ;;
      --issue-status) issue_status="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  if [[ -z "$content" ]]; then
    echo "ERROR: --content is required" >&2
    return 1
  fi

  local body
  body=$(jq -n --arg c "$content" --argjson d "$draft" '{content: $c, draft: $d}')

  if [[ -n "$issue_status" ]]; then
    body=$(echo "$body" | jq --arg s "$issue_status" '. + {issue_status: $s}')
  fi

  local result
  result=$(api_post "/v1/public/review-requests-comments/${comment_id}/replies" "$body")

  if [[ -z "$result" || "$result" == "null" ]]; then
    echo "ERROR: Failed to reply to comment $comment_id" >&2
    return 1
  fi

  echo "$result" | jq '{id: .id, status: "replied"}'
}

cmd_update_comment() {
  local comment_id="$1"
  shift

  local content="" draft="" issue_status=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --content)      content="$2"; shift 2 ;;
      --draft)        draft="$2"; shift 2 ;;
      --issue-status) issue_status="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  local body="{}"
  if [[ -n "$content" ]]; then
    body=$(echo "$body" | jq --arg c "$content" '. + {content: $c}')
  fi
  if [[ -n "$draft" ]]; then
    body=$(echo "$body" | jq --argjson d "$draft" '. + {draft: $d}')
  fi
  if [[ -n "$issue_status" ]]; then
    body=$(echo "$body" | jq --arg s "$issue_status" '. + {issue_status: $s}')
  fi

  local result
  result=$(api_patch "/v1/public/review-requests-comments/${comment_id}" "$body")

  if [[ -z "$result" || "$result" == "null" ]]; then
    echo "ERROR: Failed to update comment $comment_id" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    jq -n --arg id "$comment_id" '{"status":"updated","id":$id}'
  else
    echo "Comment $comment_id updated."
  fi
}

cmd_close_issue() {
  local comment_id="$1"

  local body
  body=$(jq -n '{issue_status: "resolved"}')

  local result
  result=$(api_patch "/v1/public/review-requests-comments/${comment_id}" "$body")

  if [[ -z "$result" || "$result" == "null" ]]; then
    echo "ERROR: Failed to close issue $comment_id" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    jq -n --arg id "$comment_id" '{"status":"resolved","id":$id}'
  else
    echo "Issue $comment_id resolved."
  fi
}

cmd_delete_comment() {
  local pr_id="$1"
  local comment_id="$2"

  api_delete "/v2/public/pull-request/${pr_id}/comment/${comment_id}"
  if [[ "$JSON_OUTPUT" == "true" ]]; then
    jq -n --arg id "$comment_id" '{"status":"deleted","id":$id}'
  else
    echo "Comment $comment_id deleted."
  fi
}

cmd_checks() {
  local pr_id="$1"
  shift

  local filter="" show_json="false"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --failed)   filter="failed"; shift ;;
      --required) filter="required"; shift ;;
      --pending)  filter="pending"; shift ;;
      --active)   filter="active"; shift ;;
      --json)     show_json="true"; shift ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  local diff_info
  diff_info=$(get_active_diff "$pr_id")
  local diff_id
  diff_id=$(echo "$diff_info" | jq -r '.id')

  local checks
  checks=$(api_get "/v1/review-requests/${pr_id}/diff-sets/${diff_id}/checks")

  if [[ -z "$checks" || "$checks" == "null" || "$checks" == "[]" ]]; then
    echo "No checks found."
    return
  fi

  # Apply filters
  local jq_filter='.'
  case "$filter" in
    failed)   jq_filter='[.[] | select(.status == "failure")]' ;;
    required) jq_filter='[.[] | select(.required == true)]' ;;
    pending)  jq_filter='[.[] | select(.status == "pending")]' ;;
    active)   jq_filter='[.[] | select(.status == "failure" or .status == "pending")]' ;;
  esac

  local filtered
  filtered=$(echo "$checks" | jq "$jq_filter")

  if [[ "$show_json" == "true" ]]; then
    echo "$filtered" | jq '[.[] | {system, type, status, required, description, system_check_uri, system_check_id, restartable}]'
    return
  fi

  # Pretty table output
  echo "$filtered" | jq -r '.[] |
    (if .status == "success" then "✅"
     elif .status == "failure" then "❌"
     elif .status == "pending" then "⏳"
     elif .status == "skipped" then "⏭️ "
     else "❓" end) + " " +
    (if .required then "[REQ]" else "[opt]" end) + " " +
    .type +
    (if .description then " — " + .description else "" end) +
    (if .system_check_uri then "\n     ↳ " + .system_check_uri else "" end)'
}

cmd_check_log() {
  local pr_id="$1"
  local check_type="$2"

  local diff_info
  diff_info=$(get_active_diff "$pr_id")
  local diff_id
  diff_id=$(echo "$diff_info" | jq -r '.id')

  local checks
  checks=$(api_get "/v1/review-requests/${pr_id}/diff-sets/${diff_id}/checks")

  # Find matching check (case-insensitive substring match)
  local check
  check=$(echo "$checks" | jq --arg t "$check_type" '[.[] | select((.type | ascii_downcase) | contains($t | ascii_downcase))]')

  local count
  count=$(echo "$check" | jq 'length')

  if [[ "$count" == "0" ]]; then
    echo "ERROR: No check matching '$check_type' found" >&2
    return 1
  fi

  if [[ "$count" -gt "1" ]]; then
    echo "Multiple checks match '$check_type':"
    echo "$check" | jq -r '.[] | "  - " + .type + " [" + .status + "]"'
    echo ""
    echo "Please specify a more precise check type."
    return 1
  fi

  # Single match — output full details
  local uri status system type desc
  uri=$(echo "$check" | jq -r '.[0].system_check_uri // empty')
  status=$(echo "$check" | jq -r '.[0].status')
  system=$(echo "$check" | jq -r '.[0].system')
  type=$(echo "$check" | jq -r '.[0].type')
  desc=$(echo "$check" | jq -r '.[0].description // empty')

  # Collect CI launch info if available
  local ci_resp=""
  if [[ -n "$uri" ]]; then
    local re='dir=([^&]+)&id=([^&]+)&number=([0-9]+)'
    if [[ "$uri" =~ $re ]]; then
      local ci_dir ci_id ci_number
      ci_dir=$(printf '%b' "${BASH_REMATCH[1]//\%/\\x}")
      ci_id="${BASH_REMATCH[2]}"
      ci_number="${BASH_REMATCH[3]}"

      local ci_token=""
      if [[ -n "${CI_OAUTH_TOKEN:-}" ]]; then
        ci_token="$CI_OAUTH_TOKEN"
      elif [[ -f "$HOME/.ci/token" ]]; then
        ci_token=$(cat "$HOME/.ci/token" | tr -d '[:space:]')
      fi

      if [[ -n "$ci_token" ]]; then
        ci_resp=$(curl -sf -H "Authorization: OAuth $ci_token" -H "Content-Type: application/json" \
          -d "{\"launch_id\":{\"action_process_id\":{\"config_path\":\"${ci_dir}/a.yaml\",\"action_id\":\"${ci_id}\"},\"launch_number\":${ci_number}}}" \
          "https://ci-public-api.yandex-team.ru/api/public/v1/ci.public_api.LaunchService/GetLaunchStatus" 2>/dev/null) || true

        if [[ -n "$ci_resp" && ("$ci_resp" == *"error"* || "$ci_resp" == *"INVALID"*) ]]; then
          ci_resp=""
        fi
      fi
    fi
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    local check_json
    check_json=$(echo "$check" | jq '.[0]')
    if [[ -n "$ci_resp" ]]; then
      jq -n --argjson check "$check_json" --argjson ci "$ci_resp" '{"check": $check, "ci_launch": $ci}'
    else
      jq -n --argjson check "$check_json" '{"check": $check}'
    fi
    return
  fi

  echo "=== Check Details ==="
  echo "System: $system"
  echo "Type:   $type"
  echo "Status: $status"
  [[ -n "$desc" ]] && echo "Description: $desc"
  [[ -n "$uri" ]] && echo "URI: $uri"

  # If it has a CI URI, show flow info
  if [[ -n "$uri" ]]; then
    local re='dir=([^&]+)&id=([^&]+)&number=([0-9]+)'
    if [[ "$uri" =~ $re ]]; then
      local ci_dir ci_id ci_number
      ci_dir=$(printf '%b' "${BASH_REMATCH[1]//\%/\\x}")
      ci_id="${BASH_REMATCH[2]}"
      ci_number="${BASH_REMATCH[3]}"
      echo ""
      echo "=== CI Flow ==="
      echo "Dir:    $ci_dir"
      echo "Flow:   $ci_id"
      echo "Number: $ci_number"

      if [[ -n "$ci_resp" ]]; then
        local ci_status ci_created ci_started
        ci_status=$(echo "$ci_resp" | jq -r '.status // empty' 2>/dev/null)
        ci_created=$(echo "$ci_resp" | jq -r '.creation_info.created_at // empty' 2>/dev/null)
        ci_started=$(echo "$ci_resp" | jq -r '.creation_info.started_at // empty' 2>/dev/null)
        echo ""
        echo "=== CI Launch Status ==="
        [[ -n "$ci_status" ]] && echo "Status:  $ci_status"
        [[ -n "$ci_created" ]] && echo "Created: $ci_created"
        [[ -n "$ci_started" ]] && echo "Started: $ci_started"

        local ci_finished ci_cancel_by ci_cancel_reason
        ci_finished=$(echo "$ci_resp" | jq -r '.finish_info.finished_at // empty' 2>/dev/null)
        ci_cancel_by=$(echo "$ci_resp" | jq -r '.cancel_info.cancelled_by // empty' 2>/dev/null)
        ci_cancel_reason=$(echo "$ci_resp" | jq -r '.cancel_info.cancel_reason // empty' 2>/dev/null)
        [[ -n "$ci_finished" ]] && echo "Finished: $ci_finished"
        [[ -n "$ci_cancel_by" ]] && echo "Cancelled by: $ci_cancel_by"
        [[ -n "$ci_cancel_reason" ]] && echo "Cancel reason: $ci_cancel_reason"
      fi
    fi
  fi
}

# --- CI/Sandbox wrappers (delegate to sandbox-cli.sh) ---
SANDBOX_CLI="$(dirname "$0")/sandbox-cli.sh"

cmd_ci_jobs() {
  local pr_id="$1"
  local check_type="${2:-}"

  if [[ -n "$check_type" ]]; then
    # Resolve check_type to action_id via Arcanum API
    local diff_info
    diff_info=$(get_active_diff "$pr_id")
    local diff_id
    diff_id=$(echo "$diff_info" | jq -r '.id')

    local checks
    checks=$(api_get "/v1/review-requests/${pr_id}/diff-sets/${diff_id}/checks")
    local check
    check=$(echo "$checks" | jq --arg t "$check_type" '[.[] | select((.type | ascii_downcase) | contains($t | ascii_downcase)) | select(.system == "CI")]')
    local count
    count=$(echo "$check" | jq 'length')

    if [[ "$count" == "0" ]]; then
      echo "ERROR: No CI check matching '$check_type' found" >&2
      return 1
    fi

    local action_id
    action_id=$(echo "$check" | jq -r '.[0].configuration.data.flow_process_id.id // empty')

    "$SANDBOX_CLI" tasks "$pr_id" "$action_id"
  else
    "$SANDBOX_CLI" tasks "$pr_id"
  fi
}

cmd_ci_log() {
  "$SANDBOX_CLI" log "$@"
}

cmd_ci_errors() {
  "$SANDBOX_CLI" errors "$@"
}

cmd_ci_failed() {
  "$SANDBOX_CLI" failed "$@"
}

cmd_open_issues() {
  local pr_id="$1"

  local comments
  comments=$(api_get "/v1/review-requests/${pr_id}/comments?fields=id,user(name,login),content,issue_status,anchor(review_request(id,diff(diff_set_xid,file(path,position(side,line,size)))))")

  if [[ -z "$comments" || "$comments" == "null" || "$comments" == "[]" ]]; then
    echo "No open issues."
    return
  fi

  local open_issues
  open_issues=$(echo "$comments" | jq '[.[] | select(.issue_status == "open") | {
    id: .id,
    author: .user.name,
    content: .content,
    file: (.anchor.review_request.diff.file.path // null),
    line: (.anchor.review_request.diff.file.position.line // null),
    side: (.anchor.review_request.diff.file.position.side // null)
  }]')

  if [[ "$open_issues" == "[]" ]]; then
    echo "No open issues."
  else
    echo "$open_issues"
  fi
}

cmd_publish_drafts() {
  local pr_id="$1"

  api_patch_no_body "/v2/public/pull-request/${pr_id}/comment/draft/publish"
  if [[ "$JSON_OUTPUT" == "true" ]]; then
    jq -n --arg pr "$pr_id" '{"status":"published","pr_id":$pr}'
  else
    echo "All draft comments published on PR $pr_id."
  fi
}

cmd_diff_comments() {
  local pr_id="$1"

  local comments
  comments=$(api_get "/v1/review-requests/${pr_id}/comments?fields=id,user(name,login),content,issue_status,anchor(review_request(id,diff(diff_set_xid,file(path,position(side,line,size)))))")

  if [[ -z "$comments" || "$comments" == "null" || "$comments" == "[]" ]]; then
    echo "No inline diff comments."
    return
  fi

  # Filter only comments with file anchors (inline diff comments)
  echo "$comments" | jq '[.[] | select(.anchor.review_request.diff.file.path != null) | {
    id: .id,
    author: .user.name,
    content: .content,
    file: .anchor.review_request.diff.file.path,
    line: .anchor.review_request.diff.file.position.line,
    side: .anchor.review_request.diff.file.position.side,
    issue_status: .issue_status
  }]'
}

cmd_worktree_create() {
  local name="$1"
  local worktree_path="${2:-}"

  if [[ -z "$name" ]]; then
    echo "ERROR: NAME or PR_ID is required" >&2
    echo "Usage: worktree-create NAME|PR_ID [PATH]" >&2
    return 1
  fi

  local branch=""
  local pr_summary=""
  local short_name=""

  # Check if input is a PR ID (all digits)
  if [[ "$name" =~ ^[0-9]+$ ]]; then
    # Fetch PR metadata to get branch name
    local pr_meta
    pr_meta=$(api_get "/v2/pull-requests/${name}?fields=vcs(from_branch),summary" 2>/dev/null) || true

    if [[ -n "$pr_meta" && "$pr_meta" != "null" ]]; then
      branch=$(echo "$pr_meta" | jq -r '.vcs.from_branch // empty')
      pr_summary=$(echo "$pr_meta" | jq -r '.summary // empty')

      if [[ -z "$branch" ]]; then
        echo "ERROR: Could not get branch for PR $name" >&2
        return 1
      fi

      # Extract ticket ID from branch for short name (e.g. users/login/QUEUE-12345 -> queue-12345)
      short_name=$(echo "$branch" | sed 's|.*/||' | tr '[:upper:]' '[:lower:]')

      echo "=== Creating worktree for PR #${name} ==="
      echo "Branch:    $branch"
      echo "Summary:   $pr_summary"
    else
      echo "ERROR: PR $name not found or API unavailable" >&2
      return 1
    fi
  else
    # Regular name input — create new branch
    short_name=$(echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
    branch="users/${USER}/${short_name}"

    echo "=== Creating worktree ==="
    echo "Branch:    $branch"
  fi

  if [[ -z "$worktree_path" ]]; then
    worktree_path="$HOME/arcadia-${short_name}"
  fi
  echo "Worktree:  $worktree_path"
  echo ""

  if [[ -d "$worktree_path" ]]; then
    echo "ERROR: Path already exists: $worktree_path" >&2
    echo "Remove it first with: arcanum-cli.sh worktree-remove $worktree_path" >&2
    return 1
  fi

  # Detect main arcadia's object store for sharing
  local main_object_store=""
  local mount_json
  mount_json=$(cd "$ARCADIA_ROOT" && arc mount --list --json 2>/dev/null) || true
  if [[ -n "$mount_json" ]]; then
    main_object_store=$(echo "$mount_json" | jq -r --arg m "$ARCADIA_ROOT" '.[] | select(.mount == $m) | ."object-store" // empty')
  fi

  # Mount new arcadia at worktree path with shared object store
  echo "Mounting arcadia at $worktree_path..."
  cd "$ARCADIA_ROOT"
  if [[ -n "$main_object_store" ]]; then
    arc mount "$worktree_path" --object-store "$main_object_store"
  else
    arc mount "$worktree_path"
  fi

  # Checkout the branch in the new worktree
  echo "Checking out branch $branch..."
  cd "$worktree_path"

  # Check if input was PR ID — checkout existing remote branch
  if [[ "$name" =~ ^[0-9]+$ ]]; then
    arc checkout "$branch"
  else
    arc checkout -b "$branch" trunk
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    jq -n --arg p "$worktree_path" --arg b "$branch" '{"path":$p,"branch":$b}'
  else
    echo ""
    echo "=== Worktree ready ==="
    echo "Path:   $worktree_path"
    echo "Branch: $branch"
    [[ -n "$pr_summary" ]] && echo "PR:     #${name} — $pr_summary"
    echo ""
    echo "To start working:"
    echo "  cd $worktree_path"
  fi
}

cmd_worktree_remove() {
  local worktree_path="$1"

  if [[ ! -d "$worktree_path" ]]; then
    echo "ERROR: Path does not exist: $worktree_path" >&2
    return 1
  fi

  # Resolve to absolute path
  worktree_path="$(cd "$worktree_path" && pwd)"

  # cd out if we're inside the worktree
  if [[ "$PWD" == "$worktree_path"* ]]; then
    cd "$HOME"
  fi

  echo "Unmounting $worktree_path..."
  arc unmount "$worktree_path" 2>/dev/null || arc unmount --force "$worktree_path" 2>/dev/null || true

  if [[ -d "$worktree_path" ]]; then
    rm -rf "$worktree_path"
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    jq -n --arg p "$worktree_path" '{"status":"removed","path":$p}'
  else
    echo "Worktree removed: $worktree_path"
  fi
}

cmd_worktree_list() {
  cd "$ARCADIA_ROOT"
  local mounts
  mounts=$(arc mount --list --json 2>/dev/null) || true

  if [[ -z "$mounts" || "$mounts" == "[]" || "$mounts" == "null" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then echo "[]"; else echo "No arc mounts found."; fi
    return
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$mounts" | jq '.'
    return
  fi

  local enrich="${1:-}"

  if [[ "$enrich" == "--status" ]]; then
    # Enriched mode: extract ticket from mount name, lookup PR status
    local tracker_cli
    tracker_cli="$(dirname "$0")/tracker-cli.sh"

    echo "=== Arc Mounts (with PR status) ==="
    local mount_paths
    mount_paths=$(echo "$mounts" | jq -r '.[].mount')

    while IFS= read -r mount_path; do
      local mount_status
      mount_status=$(echo "$mounts" | jq -r --arg m "$mount_path" '.[] | select(.mount == $m) | .status // "unknown"')
      local basename
      basename=$(echo "$mount_path" | sed 's|.*/||')

      # Extract ticket ID (e.g. QUEUE-12345 from arcadia-queue-12345)
      local ticket=""
      ticket=$(echo "$basename" | grep -oiE '[A-Z]+-[0-9]+' | head -1 | tr '[:lower:]' '[:upper:]') || true

      local pr_status="—"
      local pr_id_val=""
      if [[ -n "$ticket" && -x "$tracker_cli" ]]; then
        pr_id_val=$("$tracker_cli" pr-id "$ticket" 2>/dev/null) || true
        if [[ -n "$pr_id_val" ]]; then
          pr_status=$(api_get "/v1/pull-requests/${pr_id_val}?fields=status" 2>/dev/null | jq -r '.status // "?"') || pr_status="?"
        else
          pr_status="no PR"
        fi
      fi

      if [[ -n "$pr_id_val" ]]; then
        printf "%-10s %-50s %-16s PR #%-10s %s\n" "$mount_status" "$mount_path" "${ticket:-—}" "$pr_id_val" "$pr_status"
      else
        printf "%-10s %-50s %-16s %s\n" "$mount_status" "$mount_path" "${ticket:-—}" "$pr_status"
      fi
    done <<< "$mount_paths"
  else
    echo "=== Arc Mounts ==="
    echo "$mounts" | jq -r '.[] | "\(.mount)\t\(.branch // "detached")\t\(.status // "unknown")"' | column -t -s $'\t'
    echo ""
    echo "Tip: use --status to enrich with PR status (slower, makes API calls)"
  fi
}

# --- Main ---
usage() {
  cat <<'EOF'
Usage: arcanum-cli.sh <command> [args]

Commands:
  pr-status PR_ID                                Quick PR status (open/merged/closed/conflicts)
  pr-data PR_ID                                  PR metadata + comments
  changed-files PR_ID                            List changed files in PR
  file-diff PR_ID FILE_PATH                      Get diff for file in PR
  file-content PR_ID FILE_PATH                   Get file content at PR head
  checks PR_ID [options]                         List CI/merge checks for PR
    [--failed] [--required] [--pending] [--active] [--json]
  check-log PR_ID CHECK_TYPE                     Show details for a specific check
  ci-jobs PR_ID [CHECK_TYPE]                     List Sandbox tasks for CI checks
  ci-log TASK_ID [LOG_FILE]                      Show error logs from Sandbox task
                                                   Default: errors from execution.log + execution_error.log
                                                   LOG_FILE: execution.log, common.log, debug.log
  ci-errors TASK_ID                              Smart error analysis (format, tests, build)
  ci-failed PR_ID                                Find all failed tasks, analyze errors
  open-issues PR_ID                              List open review issues
  post-comment PR_ID --content TEXT [options]     Post comment on PR
    [--draft true|false] [--issue-status open|resolved|dropped]
    [--file PATH] [--line N] [--lines N] [--side old|new]
  reply COMMENT_ID --content TEXT [options]       Reply to comment
    [--draft true|false] [--issue-status open|resolved|dropped]
  update-comment COMMENT_ID [options]             Update existing comment
    [--content TEXT] [--draft true|false] [--issue-status STATUS]
  close-issue COMMENT_ID                          Resolve an issue
  delete-comment PR_ID COMMENT_ID                  Delete a comment
  publish-drafts PR_ID                              Publish all draft comments on PR
  diff-comments PR_ID                               List inline diff comments
  labels PR_ID [--add LABEL] [--remove LABEL]       Manage PR labels
                   [--set L1,L2]                      --add/--remove: single label; --set: replace all
  run-action PR_ID CHECK_TYPE                       Trigger an on-demand CI action (e.g. Custom testing)
  deploy-testing PR_ID SERVICE_NAME                 Add deploy:testing label + trigger Custom action
                                                      Example: deploy-testing 12345678 my-service
  worktree-create NAME|PR_ID [PATH]                Mount worktree and checkout branch
                                                   NAME: branch suffix — creates new branch from trunk
                                                   PR_ID: numeric PR ID — checks out existing PR branch
                                                   Default PATH: ~/arcadia-<name>
  worktree-remove PATH                            Unmount and remove worktree
  worktree-list [--status]                         List all arc mounts (--status: enrich with PR status)

Check filters:
  --failed     Only show checks with status=failure
  --required   Only show required checks
  --pending    Only show checks with status=pending
  --active     Show failed + pending checks (actionable)
  --json       Output raw JSON instead of pretty table

Notes:
  - file-diff and file-content require the PR commits to be fetched locally
    (run `arc pr checkout PR_ID` first if needed)
  - Auth: ARC_OAUTH_TOKEN env var, ~/.arc/token file, or `arc token show`

Environment:
  ARC_OAUTH_TOKEN    OAuth token (or save to ~/.arc/token)
  ARCADIA_ROOT       Path to arcadia mount (default: ~/arcadia)
EOF
}

cmd_labels() {
  local pr_id="$1"
  shift || true

  local action=""
  local label_name=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --add)    action="add"; label_name="$2"; shift 2 ;;
      --remove) action="remove"; label_name="$2"; shift 2 ;;
      --set)    action="set"; label_name="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  if [[ -z "$action" ]]; then
    # List labels
    local result
    result=$(curl -sf -H "$(auth_header)" "https://arcanum.yandex.net/api/v2/pull-requests/${pr_id}?fields=labels" | jq '.data.labels')
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      echo "${result:-[]}" | jq '.'
    elif [[ -z "$result" || "$result" == "null" || "$result" == "[]" ]]; then
      echo "No labels on PR $pr_id"
    else
      echo "Labels on PR $pr_id:"
      echo "$result" | jq -r '.[] | "  - " + .name'
    fi
    return
  fi

  if [[ "$action" == "add" ]]; then
    # Get current labels, add new one
    local current
    current=$(curl -sf -H "$(auth_header)" "https://arcanum.yandex.net/api/v2/pull-requests/${pr_id}?fields=labels" | jq -r '[.data.labels[]?.name]')
    local new_labels
    new_labels=$(echo "$current" | jq --arg l "$label_name" '. + [$l] | unique')
    local body
    body=$(echo "$new_labels" | jq '{labels: .}')
    curl -sf -X PUT -H "$(auth_header)" -H "Content-Type: application/json" \
      -d "$body" \
      "https://arcanum.yandex.net/api/v1/review-requests/${pr_id}/labels" >/dev/null
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      jq -n --arg l "$label_name" '{"status":"added","label":$l}'
    else
      echo "Added label '$label_name' to PR $pr_id"
    fi

  elif [[ "$action" == "remove" ]]; then
    local current
    current=$(curl -sf -H "$(auth_header)" "https://arcanum.yandex.net/api/v2/pull-requests/${pr_id}?fields=labels" | jq -r '[.data.labels[]?.name]')
    local new_labels
    new_labels=$(echo "$current" | jq --arg l "$label_name" '[.[] | select(. != $l)]')
    local body
    body=$(echo "$new_labels" | jq '{labels: .}')
    curl -sf -X PUT -H "$(auth_header)" -H "Content-Type: application/json" \
      -d "$body" \
      "https://arcanum.yandex.net/api/v1/review-requests/${pr_id}/labels" >/dev/null
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      jq -n --arg l "$label_name" '{"status":"removed","label":$l}'
    else
      echo "Removed label '$label_name' from PR $pr_id"
    fi

  elif [[ "$action" == "set" ]]; then
    # Set labels (replace all). Comma-separated.
    local labels_json
    labels_json=$(echo "$label_name" | tr ',' '\n' | jq -R . | jq -s '{labels: .}')
    curl -sf -X PUT -H "$(auth_header)" -H "Content-Type: application/json" \
      -d "$labels_json" \
      "https://arcanum.yandex.net/api/v1/review-requests/${pr_id}/labels" >/dev/null
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      jq -n --arg l "$label_name" '{"status":"set","labels":$l}'
    else
      echo "Set labels on PR $pr_id: $label_name"
    fi
  fi
}

cmd_run_action() {
  local pr_id="$1"
  local check_type="$2"

  # Get CI token
  local ci_token=""
  if [[ -n "${CI_OAUTH_TOKEN:-}" ]]; then
    ci_token="$CI_OAUTH_TOKEN"
  elif [[ -f "$HOME/.ci/token" ]]; then
    ci_token=$(cat "$HOME/.ci/token" | tr -d '[:space:]')
  fi
  if [[ -z "$ci_token" ]]; then
    echo "ERROR: CI token required (~/.ci/token or CI_OAUTH_TOKEN)" >&2
    return 1
  fi

  # Get the latest diff set ID
  local diff_id
  diff_id=$(curl -sf -H "$(auth_header)" \
    "https://arcanum.yandex.net/api/v1/review-requests/${pr_id}?fields=diff_sets(id)" | jq -r '.data.diff_sets[-1].id')

  if [[ -z "$diff_id" || "$diff_id" == "null" ]]; then
    echo "ERROR: Could not get diff set for PR $pr_id" >&2
    return 1
  fi

  # Find the matching check
  local checks
  checks=$(curl -sf -H "$(auth_header)" \
    "https://arcanum.yandex.net/api/v1/review-requests/${pr_id}/diff-sets/${diff_id}/checks" | jq '.data')

  local matching
  matching=$(echo "$checks" | jq --arg t "$check_type" '[.[] | select((.type | ascii_downcase) | contains($t | ascii_downcase))]')

  local count
  count=$(echo "$matching" | jq 'length')

  if [[ "$count" == "0" ]]; then
    echo "ERROR: No check matching '$check_type' found" >&2
    echo "Available on-demand actions:"
    echo "$checks" | jq -r '.[] | select(.configuration.on_demand == true) | "  - " + .type + " [" + .status + "]"'
    return 1
  fi

  if [[ "$count" -gt "1" ]]; then
    echo "Multiple checks match '$check_type':"
    echo "$matching" | jq -r '.[] | "  - " + .type + " [" + .status + "]"'
    echo ""
    echo "Please specify a more precise check type."
    return 1
  fi

  # Extract flow config from the check
  local config_dir config_id revision
  config_dir=$(echo "$matching" | jq -r '.[0].configuration.data.flow_process_id.dir // empty')
  config_id=$(echo "$matching" | jq -r '.[0].configuration.data.flow_process_id.id // empty')
  revision=$(echo "$matching" | jq -r '.[0].configuration.data.revision.commit_id // empty')
  local full_type
  full_type=$(echo "$matching" | jq -r '.[0].type')

  if [[ -z "$config_dir" || -z "$config_id" ]]; then
    echo "ERROR: Could not extract flow config from check" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" != "true" ]]; then
    echo "Triggering: $full_type"
    echo "  Flow: $config_dir/a.yaml :: $config_id"
    echo "  Branch: pr:$pr_id"
  fi

  # Launch via CI Public API
  local result
  result=$(curl -s -w "\n%{http_code}" -X POST \
    -H "Authorization: OAuth $ci_token" -H "Content-Type: application/json" \
    "https://ci-public-api.yandex-team.ru/api/public/v1/ci.public_api.ActionService/StartAction" \
    -d "{
      \"action_identifier\": {
        \"config_path\": \"${config_dir}/a.yaml\",
        \"action_id\": \"${config_id}\"
      },
      \"branch\": \"pr:${pr_id}\"
    }")

  local http_code
  http_code=$(echo "$result" | tail -1)
  local body
  body=$(echo "$result" | sed '$d')

  if [[ "$http_code" == "200" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      echo "$body" | jq '.'
      return
    fi

    local action_url
    action_url=$(echo "$body" | jq -r '.action_url // empty' | sed 's/\\u003d/=/g; s/\\u0026/\&/g')
    local launch_number
    launch_number=$(echo "$body" | jq -r '.action_reference.launch_number // empty')
    echo "✅ Action launched (#${launch_number})"
    [[ -n "$action_url" ]] && echo "   URL: $action_url"

    # Update Arcanum check to pending with CI flow URL
    # CI Public API StartAction doesn't link back to Arcanum automatically
    if [[ -n "$action_url" ]]; then
      echo "3. Linking check to CI flow..."
      local update_result
      update_result=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "$(auth_header)" -H "Content-Type: application/json" \
        "https://arcanum.yandex.net/api/v1/review-requests/${pr_id}/diff-sets/${diff_id}/checks" \
        -d "{
          \"system\": \"CI\",
          \"type\": \"${full_type}\",
          \"status\": \"pending\",
          \"description\": \"Running...\",
          \"system_check_uri\": \"${action_url}\"
        }")
      if [[ "$update_result" == "200" ]]; then
        echo "   ✅ Check linked to CI flow in Arcanum"
      else
        echo "   ⚠️  Could not update Arcanum check (HTTP $update_result)"
      fi
    fi
  else
    echo "ERROR: Failed to start action (HTTP $http_code)" >&2
    echo "$body"
    return 1
  fi
}

cmd_deploy_testing() {
  local pr_id="$1"
  local service_name="${2:-}"

  if [[ -z "$service_name" ]]; then
    echo "ERROR: Service name is required" >&2
    echo "Usage: arcanum-cli.sh deploy-testing PR_ID SERVICE_NAME" >&2
    echo "Example: arcanum-cli.sh deploy-testing 12345678 my-service" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" != "true" ]]; then
    echo "=== Deploy to testing: $service_name ==="
    echo "1. Adding label taxi/deploy:testing..."
  fi

  # Step 1: Add label
  cmd_labels "$pr_id" --add "taxi/deploy:testing"

  if [[ "$JSON_OUTPUT" != "true" ]]; then
    echo "2. Triggering Custom (testing) action..."
  fi

  # Step 2: Find and trigger the Custom (testing) action
  cmd_run_action "$pr_id" "Custom (testing) ($service_name)"

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    jq -n --arg pr "$pr_id" --arg svc "$service_name" '{"status":"deployed","pr_id":$pr,"service":$svc}'
  else
    echo ""
    echo "Deploy to testing initiated for $service_name on PR $pr_id"
    echo "Monitor: https://a.yandex-team.ru/review/${pr_id}/merge-checks"
  fi
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

# Allow override of arcadia root
[[ -n "${ARCADIA_ROOT_OVERRIDE:-}" ]] && ARCADIA_ROOT="$ARCADIA_ROOT_OVERRIDE"

command="$1"
shift

case "$command" in
  pr-status)       cmd_pr_status "$@" ;;
  pr-data)         cmd_pr_data "$@" ;;
  changed-files)   cmd_changed_files "$@" ;;
  file-diff)       cmd_file_diff "$@" ;;
  file-content)    cmd_file_content "$@" ;;
  checks)          cmd_checks "$@" ;;
  check-log)       cmd_check_log "$@" ;;
  ci-jobs)         cmd_ci_jobs "$@" ;;
  ci-log)          cmd_ci_log "$@" ;;
  ci-errors)       cmd_ci_errors "$@" ;;
  ci-failed)       cmd_ci_failed "$@" ;;
  open-issues)     cmd_open_issues "$@" ;;
  post-comment)    cmd_post_comment "$@" ;;
  reply)           cmd_reply "$@" ;;
  update-comment)  cmd_update_comment "$@" ;;
  close-issue)     cmd_close_issue "$@" ;;
  delete-comment)    cmd_delete_comment "$@" ;;
  publish-drafts)    cmd_publish_drafts "$@" ;;
  diff-comments)     cmd_diff_comments "$@" ;;
  labels)            cmd_labels "$@" ;;
  run-action)      cmd_run_action "$@" ;;
  deploy-testing)  cmd_deploy_testing "$@" ;;
  worktree-create) cmd_worktree_create "$@" ;;
  worktree-remove) cmd_worktree_remove "$@" ;;
  worktree-list)   cmd_worktree_list "$@" ;;
  help|--help|-h)  usage ;;
  *)
    echo "Unknown command: $command" >&2
    usage
    exit 1
    ;;
esac
