#!/usr/bin/env bash
set -euo pipefail

# --- Global state (set during argument parsing, read by cmd_* handlers) ---
JSON_OUTPUT="false"   # --json flag: switches all output to machine-readable JSON

# Tracker CLI — lightweight wrapper over Yandex Tracker REST API
# Replaces ~20 Tracker MCP tools with a single Bash script

BASE_URL="https://st-api.yandex-team.ru/v3"

# --- Auth ---
get_token() {
  if [[ -n "${TRACKER_OAUTH_TOKEN:-}" ]]; then
    echo "$TRACKER_OAUTH_TOKEN"
  elif [[ -f "$HOME/.tracker-token" ]]; then
    cat "$HOME/.tracker-token"
  else
    echo "ERROR: No Tracker token found." >&2
    echo "Set TRACKER_OAUTH_TOKEN or save token to ~/.tracker-token" >&2
    echo "Get token: https://docs.yandex-team.ru/tracker/api-ref/access#quick" >&2
    exit 1
  fi
}

TOKEN=""
auth_header() {
  [[ -z "$TOKEN" ]] && TOKEN="$(get_token)"
  echo "Authorization: OAuth $TOKEN"
}

# --- API helpers ---
# Tracker API sometimes returns unescaped control chars in JSON (tabs, newlines in descriptions).
# We sanitize U+0000..U+001F (except already-escaped ones) so jq can parse safely.
sanitize_json() {
  tr '\t' ' ' | sed $'s/[[:cntrl:]]/ /g'
}

api_get() {
  local path="$1"
  curl -sf -H "$(auth_header)" -H "Content-Type: application/json" "${BASE_URL}${path}" | sanitize_json
}

api_post() {
  local path="$1"
  local body="${2:-"{}"}"
  curl -sf -H "$(auth_header)" -H "Content-Type: application/json" -d "$body" "${BASE_URL}${path}" | sanitize_json
}

api_patch() {
  local path="$1"
  local body="${2:-"{}"}"
  curl -sf -X PATCH -H "$(auth_header)" -H "Content-Type: application/json" -d "$body" "${BASE_URL}${path}" | sanitize_json
}

api_put() {
  local path="$1"
  local body="${2:-"{}"}"
  curl -sf -X PUT -H "$(auth_header)" -H "Content-Type: application/json" -d "$body" "${BASE_URL}${path}" | sanitize_json
}

api_delete() {
  local path="$1"
  curl -s -o /dev/null -w "%{http_code}" -X DELETE -H "$(auth_header)" "${BASE_URL}${path}"
}

api_get_raw() {
  local url="$1"
  curl -sf -H "$(auth_header)" "$url"
}

# --- Commands ---

cmd_my_tasks() {
  local queue_filter=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --queue) queue_filter="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  local query="assignee:me() resolution:empty()"
  if [[ -n "$queue_filter" ]]; then
    query="$query queue:$queue_filter"
  fi

  local body
  body=$(jq -n --arg q "$query" '{"query": $q}')

  local result
  result=$(api_post "/issues/_search?perPage=50&orderBy=-updatedAt" "$body")

  if [[ -z "$result" || "$result" == "[]" ]]; then
    echo "No open tasks found."
    return
  fi

  # Group by queue
  local queues
  queues=$(echo "$result" | jq -r '.[].queue.key' | sort -u)

  for q in $queues; do
    local count
    count=$(echo "$result" | jq -r --arg q "$q" '[.[] | select(.queue.key == $q)] | length')
    echo "$q ($count open)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$result" | jq -r --arg q "$q" '
      .[] | select(.queue.key == $q) |
      "\(.key) | \(.priority.key // "normal") | \(.summary)"
    ' | while IFS='|' read -r key prio summary; do
      printf "%-20s | %-8s | %s\n" "$(echo "$key" | xargs)" "$(echo "$prio" | xargs)" "$(echo "$summary" | xargs)"
    done
    echo ""
  done
}

cmd_show() {
  local ticket_id="$1"
  shift || true
  local show_fields=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --json)   JSON_OUTPUT="true"; shift ;;
      --fields) show_fields="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  local result
  result=$(api_get "/issues/${ticket_id}")

  if [[ -z "$result" ]]; then
    echo "ERROR: Ticket $ticket_id not found" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    if [[ -n "$show_fields" ]]; then
      # Extract specific fields as JSON
      local jq_expr
      jq_expr=$(echo "$show_fields" | tr ',' '\n' | while read -r f; do echo "\"$f\": .$f"; done | paste -sd ',' -)
      echo "$result" | jq "{${jq_expr}}"
    else
      echo "$result" | jq '.'
    fi
    return
  fi

  echo "$result" | jq -r '
    "Ticket: \(.key)",
    "Summary: \(.summary)",
    "Type: \(.type.key // "?") (\(.type.display // ""))",
    "Status: \(.status.key) (\(.status.display // ""))",
    "Priority: \(.priority.key // "normal") (\(.priority.display // ""))",
    "Queue: \(.queue.key)",
    "Assignee: \(.assignee.display // "unassigned")",
    "Components: \(if .components and (.components | length > 0) then [.components[] | "\(.display // .id)"] | join(", ") else "—" end)",
    "Project: \(if .project.primary then "\(.project.primary.display // .project.primary.id)" else "—" end)",
    "Sprint: \(if .sprint and (.sprint | length > 0) then [.sprint[] | "\(.display // .id)"] | join(", ") else "—" end)",
    "Tags: \(if .tags and (.tags | length > 0) then (.tags | join(", ")) else "—" end)",
    "Created: \(.createdAt)",
    "Updated: \(.updatedAt)",
    "",
    "Description:",
    "─────────────────────────────────────",
    (.description // "(no description)")
  '
}

cmd_clone_meta() {
  local from_id="$1"
  local to_id="$2"
  shift 2
  local skip_fields=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --skip) skip_fields="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  local source
  source=$(api_get "/issues/${from_id}")
  if [[ -z "$source" ]]; then
    echo "ERROR: Source ticket $from_id not found" >&2
    return 1
  fi

  local body="{}"

  # Copy project
  if [[ ! ",$skip_fields," == *",project,"* ]]; then
    local project_id
    project_id=$(echo "$source" | jq -r '.project.primary.id // empty')
    if [[ -n "$project_id" ]]; then
      body=$(echo "$body" | jq --arg p "$project_id" '. + {project: {id: $p}}')
    fi
  fi

  # Copy priority
  if [[ ! ",$skip_fields," == *",priority,"* ]]; then
    local priority_key
    priority_key=$(echo "$source" | jq -r '.priority.key // empty')
    if [[ -n "$priority_key" ]]; then
      body=$(echo "$body" | jq --arg p "$priority_key" '. + {priority: {key: $p}}')
    fi
  fi

  # Copy components
  if [[ ! ",$skip_fields," == *",components,"* ]]; then
    local components
    components=$(echo "$source" | jq '.components // []')
    if [[ "$components" != "[]" && "$components" != "null" ]]; then
      local comp_ids
      comp_ids=$(echo "$components" | jq '[.[] | {id: (.id | tostring)}]')
      body=$(echo "$body" | jq --argjson c "$comp_ids" '. + {components: $c}')
    fi
  fi

  # Copy tags
  if [[ ! ",$skip_fields," == *",tags,"* ]]; then
    local tags
    tags=$(echo "$source" | jq '.tags // []')
    if [[ "$tags" != "[]" && "$tags" != "null" ]]; then
      body=$(echo "$body" | jq --argjson t "$tags" '. + {tags: $t}')
    fi
  fi

  if [[ "$body" == "{}" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      echo '{"status":"cloned","from":"'"$from_id"'","to":"'"$to_id"'","fields":[]}'
    else
      echo "Nothing to copy."
    fi
    return
  fi

  local result
  result=$(api_patch "/issues/${to_id}" "$body")
  if [[ -z "$result" ]]; then
    echo "ERROR: Failed to update $to_id" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    local fields_json
    fields_json=$(echo "$body" | jq '[keys[]]')
    jq -n --arg from "$from_id" --arg to "$to_id" --argjson fields "$fields_json" \
      '{"status":"cloned","from":$from,"to":$to,"fields":$fields}'
    return
  fi

  echo "Copied metadata from $from_id to $to_id"
  echo "$body" | jq -r 'keys[] | "  ✓ \(.)"'
}

cmd_links() {
  local ticket_id="$1"
  local result
  result=$(api_get "/issues/${ticket_id}/links")

  if [[ -z "$result" || "$result" == "[]" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then echo "[]"; else echo "No linked issues for $ticket_id"; fi
    return
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "Linked issues for $ticket_id:"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "$result" | jq -r '
    .[] |
    "\(.type.display // .type.id): \(.object.key) — \(.object.display // "")"
  '
}

cmd_status() {
  local ticket_id="$1"
  local status="$2"
  shift 2

  # Collect extra fields: --field key=value → {"key": value}
  local body="{}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --field)
        local key="${2%%=*}"
        local val="${2#*=}"
        body=$(echo "$body" | jq --arg k "$key" --argjson v "$val" '. + {($k): $v}')
        shift 2
        ;;
      *) shift ;;
    esac
  done

  local response http_code
  response=$(curl -s -w "\n%{http_code}" \
    -H "$(auth_header)" -H "Content-Type: application/json" \
    -d "$body" \
    "${BASE_URL}/issues/${ticket_id}/transitions/${status}/_execute" | sanitize_json)
  http_code=$(echo "$response" | tail -1)
  local resp_body
  resp_body=$(echo "$response" | sed '$d')

  if [[ "$http_code" == "200" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      echo "$resp_body" | jq '.'
    else
      echo "Status changed: $ticket_id → $status"
    fi
  else
    # Show API error message if available
    local err_msg
    err_msg=$(echo "$resp_body" | jq -r '.errorMessages[]? // empty' 2>/dev/null)
    if [[ -n "$err_msg" ]]; then
      echo "ERROR ($http_code): $err_msg" >&2
    else
      echo "ERROR: Failed to change status for $ticket_id → $status (HTTP $http_code)" >&2
    fi
    echo "" >&2
    echo "Available transitions:" >&2
    api_get "/issues/${ticket_id}/transitions" | jq -r '.[].id' 2>/dev/null || true
    return 1
  fi
}

cmd_search() {
  local query="" fields="" page="" per_page="" order=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --query)    query="$2"; shift 2 ;;
      --fields)   fields="$2"; shift 2 ;;
      --page)     page="$2"; shift 2 ;;
      --per-page) per_page="$2"; shift 2 ;;
      --order)    order="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  if [[ -z "$query" ]]; then
    echo "ERROR: --query is required" >&2
    return 1
  fi

  local body
  body=$(jq -n --arg q "$query" '{"query": $q}')

  local params="perPage=${per_page:-20}"
  [[ -n "$page" ]] && params="${params}&page=${page}"
  [[ -n "$order" ]] && params="${params}&orderBy=${order}"

  local result
  result=$(api_post "/issues/_search?${params}" "$body")

  if [[ -z "$result" || "$result" == "[]" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then echo "[]"; else echo "No issues found."; fi
    return
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  # If fields specified, filter output
  if [[ -n "$fields" ]]; then
    # Convert comma-separated fields to jq select
    local jq_fields
    jq_fields=$(echo "$fields" | tr ',' '\n' | sed 's/.*/.&/' | tr '\n' ',' | sed 's/,$//')
    echo "$result" | jq "[.[] | {${jq_fields}}]"
  else
    # Default: show key, status, summary
    echo "$result" | jq -r '
      .[] |
      "\(.key) | \(.status.key // "?") | \(.summary)"
    ' | while IFS='|' read -r key status summary; do
      printf "%-20s | %-14s | %s\n" "$(echo "$key" | xargs)" "$(echo "$status" | xargs)" "$(echo "$summary" | xargs)"
    done
  fi
}

cmd_create() {
  local queue="" summary="" description="" type="" priority="" parent="" tags=""
  local components="" project="" sprint="" boards=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --queue)       queue="$2"; shift 2 ;;
      --summary)     summary="$2"; shift 2 ;;
      --description) description="$2"; shift 2 ;;
      --type)        type="$2"; shift 2 ;;
      --priority)    priority="$2"; shift 2 ;;
      --parent)      parent="$2"; shift 2 ;;
      --tags)        tags="$2"; shift 2 ;;
      --components)  components="$2"; shift 2 ;;
      --project)     project="$2"; shift 2 ;;
      --sprint)      sprint="$2"; shift 2 ;;
      --boards)      boards="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  if [[ -z "$queue" || -z "$summary" || -z "$type" ]]; then
    echo "ERROR: --queue, --summary, and --type are required" >&2
    return 1
  fi

  local body
  body=$(jq -n \
    --arg q "$queue" \
    --arg s "$summary" \
    --arg d "${description:-}" \
    --arg t "$type" \
    '{queue: {key: $q}, summary: $s, description: $d, type: {key: $t}}')

  if [[ -n "$priority" ]]; then
    body=$(echo "$body" | jq --arg p "$priority" '. + {priority: {key: $p}}')
  fi
  if [[ -n "$parent" ]]; then
    body=$(echo "$body" | jq --arg p "$parent" '. + {parent: {key: $p}}')
  fi
  if [[ -n "$tags" ]]; then
    local tags_json
    tags_json=$(echo "$tags" | tr ',' '\n' | jq -R . | jq -s .)
    body=$(echo "$body" | jq --argjson t "$tags_json" '. + {tags: $t}')
  fi
  if [[ -n "$components" ]]; then
    local comp_json
    comp_json=$(echo "$components" | tr ',' '\n' | jq -R '{id: .}' | jq -s .)
    body=$(echo "$body" | jq --argjson c "$comp_json" '. + {components: $c}')
  fi
  if [[ -n "$project" ]]; then
    body=$(echo "$body" | jq --arg p "$project" '. + {project: {id: $p}}')
  fi
  if [[ -n "$sprint" ]]; then
    local sprint_json
    sprint_json=$(echo "$sprint" | tr ',' '\n' | jq -R '{id: .}' | jq -s .)
    body=$(echo "$body" | jq --argjson s "$sprint_json" '. + {sprint: $s}')
  fi

  local result
  result=$(api_post "/issues" "$body")

  if [[ -z "$result" ]]; then
    echo "ERROR: Failed to create issue" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "$result" | jq -r '"Created: \(.key) — \(.summary)"'

  # Add to boards if specified (boards are managed via separate API)
  if [[ -n "$boards" ]]; then
    local issue_key
    issue_key=$(echo "$result" | jq -r '.key')
    for board_id in $(echo "$boards" | tr ',' ' '); do
      curl -s -o /dev/null -X POST \
        -H "$(auth_header)" -H "Content-Type: application/json" \
        -d "{\"issue\": \"$issue_key\"}" \
        "${BASE_URL}/boards/${board_id}/issues"
      # Verify by checking the ticket, not the HTTP code (API returns non-2xx even on success)
      if api_get "/issues/${issue_key}" | jq -e ".boards[]? | select(.id == $board_id)" >/dev/null 2>&1; then
        echo "  Added to board $board_id"
      else
        echo "  WARNING: Could not add to board $board_id" >&2
      fi
    done
  fi
}

cmd_update() {
  local ticket_id="${1:-}"
  shift || true

  if [[ -z "$ticket_id" ]]; then
    echo "ERROR: TICKET-ID is required" >&2
    return 1
  fi

  local body="{}"
  local _boards_to_add=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --field)
        local raw="$2"
        local key="${raw%%=*}"
        local val="${raw#*=}"
        shift 2

        # Handle special value formats:
        # assignee:login → {"id": "login"}
        # priority:high → {"key": "high"}
        # tags:+new → add tag
        # tags:-old → remove tag
        if [[ "$key" == "assignee" || "$key" == "createdBy" || "$key" == "updatedBy" || "$key" == "author" ]]; then
          body=$(echo "$body" | jq --arg k "$key" --arg v "$val" '. + {($k): {id: $v}}')
        elif [[ "$key" == "priority" || "$key" == "type" || "$key" == "status" ]]; then
          body=$(echo "$body" | jq --arg k "$key" --arg v "$val" '. + {($k): {key: $v}}')
        elif [[ "$key" == "components" || "$key" == "sprint" ]]; then
          # List of objects with id: components=180033,180034 or sprint=350183
          local items_json
          items_json=$(echo "$val" | tr ',' '\n' | jq -R '{id: .}' | jq -s .)
          body=$(echo "$body" | jq --arg k "$key" --argjson v "$items_json" '. + {($k): $v}')
        elif [[ "$key" == "project" ]]; then
          body=$(echo "$body" | jq --arg k "$key" --arg v "$val" '. + {($k): {id: $v}}')
        elif [[ "$key" == "boards" ]]; then
          # Boards are handled after the main update
          _boards_to_add="$val"
          shift 0  # no-op, just store for later
        elif [[ "$val" == +* ]]; then
          # List add: tags:+newtag
          local add_val="${val:1}"
          body=$(echo "$body" | jq --arg k "$key" --arg v "$add_val" '. + {($k): {add: [$v]}}')
        elif [[ "$val" == -* ]]; then
          # List remove: tags:-oldtag
          local rm_val="${val:1}"
          body=$(echo "$body" | jq --arg k "$key" --arg v "$rm_val" '. + {($k): {remove: [$v]}}')
        else
          body=$(echo "$body" | jq --arg k "$key" --arg v "$val" '. + {($k): $v}')
        fi
        ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  local result
  result=$(api_patch "/issues/${ticket_id}" "$body")

  if [[ -z "$result" ]]; then
    echo "ERROR: Failed to update $ticket_id" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    # Still handle boards silently
  else
    echo "$result" | jq -r '"Updated: \(.key) — \(.summary)"'
  fi

  # Add to boards if specified
  if [[ -n "$_boards_to_add" ]]; then
    for board_id in $(echo "$_boards_to_add" | tr ',' ' '); do
      curl -s -o /dev/null -X POST \
        -H "$(auth_header)" -H "Content-Type: application/json" \
        -d "{\"issue\": \"$ticket_id\"}" \
        "${BASE_URL}/boards/${board_id}/issues"
      # Verify by checking the ticket, not the HTTP code (API returns non-2xx even on success)
      if api_get "/issues/${ticket_id}" | jq -e ".boards[]? | select(.id == $board_id)" >/dev/null 2>&1; then
        echo "  Added to board $board_id"
      else
        echo "  WARNING: Could not add to board $board_id" >&2
      fi
    done
  fi
}

cmd_comment() {
  local ticket_id="${1:-}"
  shift || true

  if [[ -z "$ticket_id" ]]; then
    echo "ERROR: TICKET-ID is required" >&2
    return 1
  fi

  local text="" summonees=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --text)      text="$2"; shift 2 ;;
      --summonees) summonees="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  if [[ -z "$text" ]]; then
    echo "ERROR: --text is required" >&2
    return 1
  fi

  local body
  body=$(jq -n --arg t "$text" '{text: $t}')

  if [[ -n "$summonees" ]]; then
    local summ_json
    summ_json=$(echo "$summonees" | tr ',' '\n' | jq -R '{id: .}' | jq -s .)
    body=$(echo "$body" | jq --argjson s "$summ_json" '. + {summonees: $s}')
  fi

  local result
  result=$(api_post "/issues/${ticket_id}/comments" "$body")

  if [[ -z "$result" ]]; then
    echo "ERROR: Failed to add comment to $ticket_id" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "$result" | jq -r '"Comment added to \(.self | split("/") | .[-3]) (id: \(.longId // .id))"'
}

cmd_comment_update() {
  local ticket_id="${1:-}"
  shift || true

  if [[ -z "$ticket_id" ]]; then
    echo "ERROR: TICKET-ID is required" >&2
    return 1
  fi

  local comment_id="" text=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id)   comment_id="$2"; shift 2 ;;
      --text) text="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  if [[ -z "$comment_id" || -z "$text" ]]; then
    echo "ERROR: --id and --text are required" >&2
    return 1
  fi

  local body
  body=$(jq -n --arg t "$text" '{text: $t}')

  local result
  result=$(api_patch "/issues/${ticket_id}/comments/${comment_id}" "$body")

  if [[ -z "$result" ]]; then
    echo "ERROR: Failed to update comment" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "Comment $comment_id updated."
}

cmd_comment_delete() {
  local ticket_id="${1:-}"
  shift || true

  if [[ -z "$ticket_id" ]]; then
    echo "ERROR: TICKET-ID is required" >&2
    return 1
  fi

  local comment_id=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id)   comment_id="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  if [[ -z "$comment_id" ]]; then
    echo "ERROR: --id is required" >&2
    return 1
  fi

  local http_code
  http_code=$(api_delete "/issues/${ticket_id}/comments/${comment_id}")

  if [[ "$http_code" == "204" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      echo '{"status":"deleted"}'
    else
      echo "Comment $comment_id deleted."
    fi
  else
    echo "ERROR: Failed to delete comment $comment_id (HTTP $http_code)" >&2
    return 1
  fi
}

cmd_link() {
  local ticket_id="${1:-}"
  shift || true

  if [[ -z "$ticket_id" ]]; then
    echo "ERROR: TICKET-ID is required" >&2
    return 1
  fi

  local target="" link_type=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --to)   target="$2"; shift 2 ;;
      --type) link_type="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  if [[ -z "$target" || -z "$link_type" ]]; then
    echo "ERROR: --to and --type are required" >&2
    return 1
  fi

  local body
  body=$(jq -n --arg t "$target" --arg r "$link_type" '{issue: $t, relationship: $r}')

  local result
  result=$(api_post "/issues/${ticket_id}/links" "$body")

  if [[ -z "$result" ]]; then
    echo "ERROR: Failed to create link" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "Link created: $ticket_id → ($link_type) → $target"
}

cmd_changelog() {
  local ticket_id="${1:-}"
  shift || true

  if [[ -z "$ticket_id" ]]; then
    echo "ERROR: TICKET-ID is required" >&2
    return 1
  fi

  local field="" change_type="" per_page="" last_n=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --field)    field="$2"; shift 2 ;;
      --type)     change_type="$2"; shift 2 ;;
      --per-page) per_page="$2"; shift 2 ;;
      --last)     last_n="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  local params=""
  [[ -n "$per_page" ]] && params="perPage=${per_page}"
  [[ -n "$field" ]] && params="${params:+${params}&}field=${field}"
  [[ -n "$change_type" ]] && params="${params:+${params}&}type=${change_type}"

  local path="/issues/${ticket_id}/changelog"
  [[ -n "$params" ]] && path="${path}?${params}"

  local result
  result=$(api_get "$path")

  if [[ -z "$result" || "$result" == "[]" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then echo "[]"; else echo "No changelog entries for $ticket_id"; fi
    return
  fi

  # Apply --last filter client-side
  if [[ -n "$last_n" ]]; then
    result=$(echo "$result" | jq ".[-${last_n}:]")
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "$result" | jq -r '
    def fmt_val:
      if . == null then "∅"
      elif type == "object" then (.display // .key // (.id | tostring) // "∅")
      elif type == "array" then ([.[]? | if type == "object" then (.display // .key // "") else tostring end] | join(","))
      elif type == "string" then .
      else tostring end;
    .[] |
    "\(.updatedAt) | \(.type) | \(.updatedBy.display // .updatedBy.id // "unknown") | \([.fields[]? | "\(.field.display // .field.id): \(.from | fmt_val) → \(.to | fmt_val)"] | join(", "))"
  '
}

cmd_attachment() {
  local ticket_id="${1:-}"
  shift || true

  if [[ -z "$ticket_id" ]]; then
    echo "ERROR: TICKET-ID is required" >&2
    return 1
  fi

  local att_id=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id) att_id="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  if [[ -n "$att_id" ]]; then
    # Single attachment metadata
    local result
    result=$(api_get "/issues/${ticket_id}/attachments/${att_id}")
    echo "$result" | jq .
  else
    # List all attachments
    local result
    result=$(api_get "/issues/${ticket_id}/attachments")
    if [[ -z "$result" || "$result" == "[]" ]]; then
      if [[ "$JSON_OUTPUT" == "true" ]]; then echo "[]"; else echo "No attachments for $ticket_id"; fi
      return
    fi
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      echo "$result" | jq '.'
      return
    fi
    echo "$result" | jq -r '.[] | "\(.id) | \(.name) | \(.size) bytes | \(.createdAt)"'
  fi
}

cmd_attachment_content() {
  local att_id=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id) att_id="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  if [[ -z "$att_id" ]]; then
    echo "ERROR: --id is required" >&2
    return 1
  fi

  # First get attachment metadata to find the download URL
  local meta
  meta=$(curl -sf -H "$(auth_header)" "${BASE_URL}/attachments/${att_id}" | sanitize_json)

  if [[ -z "$meta" ]]; then
    echo "ERROR: Attachment $att_id not found" >&2
    return 1
  fi

  local download_url
  download_url=$(echo "$meta" | jq -r '.self // empty')
  local filename
  filename=$(echo "$meta" | jq -r '.name // "attachment"')

  if [[ -n "$download_url" ]]; then
    api_get_raw "${download_url}/${filename}"
  else
    echo "ERROR: Could not determine download URL" >&2
    return 1
  fi
}

# --- Project commands ---

cmd_projects() {
  local per_page="" page="" expand=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --per-page) per_page="$2"; shift 2 ;;
      --page)     page="$2"; shift 2 ;;
      --expand)   expand="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  local params=""
  [[ -n "$per_page" ]] && params="perPage=${per_page}"
  [[ -n "$page" ]] && params="${params:+${params}&}page=${page}"
  [[ -n "$expand" ]] && params="${params:+${params}&}expand=${expand}"

  local path="/projects"
  [[ -n "$params" ]] && path="${path}?${params}"

  local result
  result=$(api_get "$path")

  if [[ -z "$result" || "$result" == "[]" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then echo "[]"; else echo "No projects found."; fi
    return
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "$result" | jq -r '
    .[] |
    "\(.id) | \(.status // "?") | \(.name) | \(.lead.display // "no lead")"
  ' | while IFS='|' read -r id status name lead; do
    printf "%-8s | %-14s | %-40s | %s\n" "$(echo "$id" | xargs)" "$(echo "$status" | xargs)" "$(echo "$name" | xargs)" "$(echo "$lead" | xargs)"
  done
}

cmd_project_show() {
  local project_id="${1:-}"
  shift || true

  if [[ -z "$project_id" ]]; then
    echo "ERROR: PROJECT-ID is required" >&2
    return 1
  fi

  local expand=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --expand) expand="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  local path="/projects/${project_id}"
  [[ -n "$expand" ]] && path="${path}?expand=${expand}"

  local result
  result=$(api_get "$path")

  if [[ -z "$result" ]]; then
    echo "ERROR: Project $project_id not found" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "$result" | jq -r '
    "Project: \(.id)",
    "Name: \(.name)",
    "Key: \(.key // "")",
    "Status: \(.status // "?")",
    "Lead: \(.lead.display // "unassigned")",
    "Start: \(.startDate // "not set")",
    "End: \(.endDate // "not set")",
    "Version: \(.version)",
    "",
    "Description:",
    "─────────────────────────────────────",
    (.description // "(no description)")
  '
}

cmd_project_create() {
  local name="" queues="" description="" lead="" status="" start_date="" end_date=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --name)        name="$2"; shift 2 ;;
      --queues)      queues="$2"; shift 2 ;;
      --description) description="$2"; shift 2 ;;
      --lead)        lead="$2"; shift 2 ;;
      --status)      status="$2"; shift 2 ;;
      --start-date)  start_date="$2"; shift 2 ;;
      --end-date)    end_date="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  if [[ -z "$name" || -z "$queues" ]]; then
    echo "ERROR: --name and --queues are required" >&2
    return 1
  fi

  local body
  body=$(jq -n --arg n "$name" --arg q "$queues" '{name: $n, queues: $q}')

  [[ -n "$description" ]] && body=$(echo "$body" | jq --arg v "$description" '. + {description: $v}')
  [[ -n "$lead" ]] && body=$(echo "$body" | jq --arg v "$lead" '. + {lead: $v}')
  [[ -n "$status" ]] && body=$(echo "$body" | jq --arg v "$status" '. + {status: $v}')
  [[ -n "$start_date" ]] && body=$(echo "$body" | jq --arg v "$start_date" '. + {startDate: $v}')
  [[ -n "$end_date" ]] && body=$(echo "$body" | jq --arg v "$end_date" '. + {endDate: $v}')

  local result
  result=$(api_post "/projects" "$body")

  if [[ -z "$result" ]]; then
    echo "ERROR: Failed to create project" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "$result" | jq -r '"Created project: \(.id) — \(.name)"'
}

cmd_project_update() {
  local project_id="${1:-}"
  shift || true

  if [[ -z "$project_id" ]]; then
    echo "ERROR: PROJECT-ID is required" >&2
    return 1
  fi

  local version="" name="" queues="" description="" lead="" status="" start_date="" end_date=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --version)     version="$2"; shift 2 ;;
      --name)        name="$2"; shift 2 ;;
      --queues)      queues="$2"; shift 2 ;;
      --description) description="$2"; shift 2 ;;
      --lead)        lead="$2"; shift 2 ;;
      --status)      status="$2"; shift 2 ;;
      --start-date)  start_date="$2"; shift 2 ;;
      --end-date)    end_date="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  # If version not provided, fetch current version
  if [[ -z "$version" ]]; then
    version=$(api_get "/projects/${project_id}" | jq -r '.version')
    if [[ -z "$version" || "$version" == "null" ]]; then
      echo "ERROR: Could not determine project version. Use --version." >&2
      return 1
    fi
  fi

  local body="{}"
  [[ -n "$name" ]] && body=$(echo "$body" | jq --arg v "$name" '. + {name: $v}')
  [[ -n "$queues" ]] && body=$(echo "$body" | jq --arg v "$queues" '. + {queues: $v}')
  [[ -n "$description" ]] && body=$(echo "$body" | jq --arg v "$description" '. + {description: $v}')
  [[ -n "$lead" ]] && body=$(echo "$body" | jq --arg v "$lead" '. + {lead: $v}')
  [[ -n "$status" ]] && body=$(echo "$body" | jq --arg v "$status" '. + {status: $v}')
  [[ -n "$start_date" ]] && body=$(echo "$body" | jq --arg v "$start_date" '. + {startDate: $v}')
  [[ -n "$end_date" ]] && body=$(echo "$body" | jq --arg v "$end_date" '. + {endDate: $v}')

  local result
  result=$(api_put "/projects/${project_id}?version=${version}" "$body")

  if [[ -z "$result" ]]; then
    echo "ERROR: Failed to update project $project_id" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "$result" | jq -r '"Updated project: \(.id) — \(.name)"'
}

cmd_project_delete() {
  local project_id="${1:-}"

  if [[ -z "$project_id" ]]; then
    echo "ERROR: PROJECT-ID is required" >&2
    return 1
  fi

  local http_code
  http_code=$(api_delete "/projects/${project_id}")

  if [[ "$http_code" == "200" || "$http_code" == "204" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      echo '{"status":"deleted"}'
    else
      echo "Project $project_id deleted."
    fi
  else
    echo "ERROR: Failed to delete project $project_id (HTTP $http_code)" >&2
    return 1
  fi
}

cmd_project_queues() {
  local project_id="${1:-}"

  if [[ -z "$project_id" ]]; then
    echo "ERROR: PROJECT-ID is required" >&2
    return 1
  fi

  local result
  result=$(api_get "/projects/${project_id}/queues")

  if [[ -z "$result" || "$result" == "[]" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then echo "[]"; else echo "No queues in project $project_id"; fi
    return
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "Queues in project $project_id:"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "$result" | jq -r '.[] | "\(.key) — \(.name // "")"'
}

cmd_transitions() {
  local ticket_id="${1:-}"

  if [[ -z "$ticket_id" ]]; then
    echo "ERROR: TICKET-ID is required" >&2
    return 1
  fi

  local result
  result=$(api_get "/issues/${ticket_id}/transitions")

  if [[ -z "$result" || "$result" == "[]" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then echo "[]"; else echo "No transitions available for $ticket_id"; fi
    return
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "Available transitions for $ticket_id:"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "$result" | jq -r '.[] | "\(.id) → \(.to.display // .to.key)"'
}

# --- Main ---
usage() {
  cat <<'EOF'
Usage: tracker-cli.sh <command> [args]

Commands:
  my-tasks [--queue QUEUE]                       List my open tasks
  show TICKET [--json] [--fields f1,f2]           Show ticket details
                                                   --json: raw JSON output
                                                   --fields: specific fields only (with --json)
  clone-meta FROM_TICKET TO_TICKET [--skip f,..] Copy metadata (project, priority, components, tags)
  links TICKET                                   Show linked issues
  pr-id TICKET                                   Get Arcanum PR ID linked to ticket
  status TICKET STATUS [--field k=v]             Change ticket status
  transitions TICKET                             List available transitions
  search --query QUERY [--fields f1,f2]          Search issues
         [--page N] [--per-page N] [--order F]
  create --queue Q --summary S --type T          Create new issue
         [--description D] [--priority P]
         [--parent KEY] [--tags t1,t2]
         [--components ID,...] [--project ID]
         [--sprint ID,...] [--boards ID,...]
  update TICKET --field key=value ...            Update issue fields
  comment TICKET --text TEXT [--summonees u1,u2] Add comment
  comment-update TICKET --id ID --text TEXT      Update comment
  comment-delete TICKET --id ID                  Delete comment
  link TICKET --to TARGET --type TYPE            Create issue link
  changelog TICKET [--field F] [--type T]        Show change history
            [--per-page N] [--last N]
  attachment TICKET [--id ATT_ID]                List/show attachments
  attachment-content --id ATT_ID                 Download attachment content

Projects:
  projects [--per-page N] [--page N]             List projects
           [--expand queues]
  project-show ID [--expand queues]              Show project details
  project-create --name N --queues Q             Create project
                 [--description D] [--lead L]
                 [--status S] [--start-date D]
                 [--end-date D]
  project-update ID [--version V] [--name N]     Update project
                 [--queues Q] [--description D]
                 [--lead L] [--status S]
                 [--start-date D] [--end-date D]
  project-delete ID                              Delete project
  project-queues ID                              List project queues

Environment:
  TRACKER_OAUTH_TOKEN    OAuth token (or save to ~/.tracker-token)

Update field value formats:
  --field summary="New title"      Scalar value
  --field assignee=login           User field (auto-wrapped as {id: ...})
  --field priority=high            Enum field (auto-wrapped as {key: ...})
  --field tags=+newtag             Add to list
  --field tags=-oldtag             Remove from list
  --field components=ID1,ID2       Set components by ID
  --field project=ID               Set project by ID
  --field sprint=ID1,ID2           Set sprints by ID
  --field boards=ID1,ID2           Add to boards by ID

Link types: "depends on", "is dependent by", "relates"
EOF
}

cmd_pr_id() {
  local ticket_id="$1"
  if [[ -z "$ticket_id" ]]; then
    echo "Usage: tracker-cli.sh pr-id TICKET" >&2
    exit 1
  fi

  local result
  result=$(api_get "/issues/${ticket_id}/remotelinks")

  if [[ -z "$result" || "$result" == "null" || "$result" == "[]" ]]; then
    echo "No remote links found for $ticket_id" >&2
    return 1
  fi

  # Filter Arcanum links and extract PR IDs
  local pr_ids
  pr_ids=$(echo "$result" | jq -r '[.[] | select(.object.application.type == "ru.yandex.arcanum") | .object.key] | .[]')

  if [[ -z "$pr_ids" ]]; then
    echo "No Arcanum PR linked to $ticket_id" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$pr_ids" | jq -R . | jq -s '{pr_ids:.}'
    return
  fi

  echo "$pr_ids"
}

cmd_remotelinks() {
  local ticket="$1"
  if [[ -z "$ticket" ]]; then
    echo "Usage: tracker-cli.sh remotelinks TICKET" >&2
    exit 1
  fi

  local result
  result=$(api_get "/issues/${ticket}/remotelinks")

  if [[ -z "$result" || "$result" == "null" || "$result" == "[]" ]]; then
    echo "No remote links for $ticket"
    return 0
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result"
    return
  fi

  echo "Remote links for ${ticket}:"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "$result" | jq -r '.[] | "id=\(.id) app=\(.object.application.type) key=\(.object.key) rel=\(.type.id)"'
}

cmd_remotelink_add() {
  local ticket="" key="" origin="" relationship="relates"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --key)          key="$2"; shift 2 ;;
      --origin)       origin="$2"; shift 2 ;;
      --relationship) relationship="$2"; shift 2 ;;
      -*) echo "Unknown option: $1" >&2; exit 1 ;;
      *) ticket="$1"; shift ;;
    esac
  done

  if [[ -z "$ticket" || -z "$key" || -z "$origin" ]]; then
    echo "Usage: tracker-cli.sh remotelink-add TICKET --key KEY --origin ORIGIN [--relationship TYPE]" >&2
    echo "  Example: tracker-cli.sh remotelink-add TICKET-123 --key 12464078 --origin ru.yandex.arcanum" >&2
    exit 1
  fi

  local body
  body=$(jq -n --arg rel "$relationship" --arg key "$key" --arg origin "$origin" \
    '{relationship: $rel, key: $key, origin: $origin}')

  local result
  result=$(api_post "/issues/${ticket}/remotelinks" "$body")

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "$result" | jq -r '"Remote link created: id=\(.id) key=\(.object.key) app=\(.object.application.type)"' 2>/dev/null || echo "$result"
}

cmd_remotelink_remove() {
  local ticket="" link_id=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id) link_id="$2"; shift 2 ;;
      -*) echo "Unknown option: $1" >&2; exit 1 ;;
      *) ticket="$1"; shift ;;
    esac
  done

  if [[ -z "$ticket" || -z "$link_id" ]]; then
    echo "Usage: tracker-cli.sh remotelink-remove TICKET --id LINK_ID" >&2
    exit 1
  fi

  local http_code
  http_code=$(api_delete "/issues/${ticket}/remotelinks/${link_id}")

  if [[ "$http_code" == "204" || "$http_code" == "200" ]]; then
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      echo '{"status":"deleted"}'
    else
      echo "Remote link ${link_id} removed from ${ticket}"
    fi
  else
    echo "Failed to remove remote link (HTTP ${http_code})" >&2
    return 1
  fi
}

cmd_comments() {
  local ticket=""
  local per_page=50
  local page=1
  local order="asc"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --per-page) per_page="$2"; shift 2 ;;
      --page) page="$2"; shift 2 ;;
      --order) order="$2"; shift 2 ;;
      -*) echo "Unknown option: $1" >&2; exit 1 ;;
      *) ticket="$1"; shift ;;
    esac
  done

  if [[ -z "$ticket" ]]; then
    echo "Usage: tracker-cli.sh comments TICKET [--per-page N] [--page N] [--order asc|desc]" >&2
    exit 1
  fi

  local result
  result=$(api_get "/issues/${ticket}/comments?perPage=${per_page}&page=${page}&order=${order}")

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$result" | jq '.'
    return
  fi

  echo "$result" | jq -r '.[] | "---\nDate: \(.createdAt)\nAuthor: \(.createdBy.display // .createdBy.id)\n\(.text // "(no text)")\n"'
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

# Global flags must come before the command name:
#   tracker-cli.sh --json show TICKET
while [[ $# -gt 0 && "$1" == --* ]]; do
  case "$1" in
    --json) JSON_OUTPUT="true"; shift ;;
    *) break ;;
  esac
done

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

command="$1"
shift

case "$command" in
  my-tasks)           cmd_my_tasks "$@" ;;
  show)               cmd_show "$@" ;;
  clone-meta)         cmd_clone_meta "$@" ;;
  links)              cmd_links "$@" ;;
  pr-id)              cmd_pr_id "$@" ;;
  status)             cmd_status "$@" ;;
  transitions)        cmd_transitions "$@" ;;
  search)             cmd_search "$@" ;;
  create)             cmd_create "$@" ;;
  update)             cmd_update "$@" ;;
  comment)            cmd_comment "$@" ;;
  comment-update)     cmd_comment_update "$@" ;;
  comment-delete)     cmd_comment_delete "$@" ;;
  comments)           cmd_comments "$@" ;;
  link)               cmd_link "$@" ;;
  changelog)          cmd_changelog "$@" ;;
  attachment)         cmd_attachment "$@" ;;
  attachment-content) cmd_attachment_content "$@" ;;
  projects)           cmd_projects "$@" ;;
  project-show)       cmd_project_show "$@" ;;
  project-create)     cmd_project_create "$@" ;;
  project-update)     cmd_project_update "$@" ;;
  project-delete)     cmd_project_delete "$@" ;;
  project-queues)     cmd_project_queues "$@" ;;
  help|--help|-h)     usage ;;
  *)
    echo "Unknown command: $command" >&2
    usage
    exit 1
    ;;
esac
