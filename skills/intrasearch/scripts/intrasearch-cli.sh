#!/usr/bin/env bash
set -euo pipefail

# Intrasearch CLI — lightweight wrapper over Intrasearch REST API
# Replaces 4 Intrasearch MCP tools with a single Bash script
# API: GET https://search-back.yandex-team.ru/suggest/

BASE_URL="https://search-back.yandex-team.ru/suggest/"

# --- Auth ---
get_token() {
  if [[ -n "${INTRASEARCH_TOKEN:-}" ]]; then
    echo "$INTRASEARCH_TOKEN"
  elif [[ -f "$HOME/.mcp_store/oauth_token" ]]; then
    cat "$HOME/.mcp_store/oauth_token"
  else
    echo "ERROR: No OAuth token found." >&2
    echo "Set INTRASEARCH_TOKEN or save to ~/.mcp_store/oauth_token" >&2
    exit 1
  fi
}

TOKEN=""
JSON_OUTPUT="false"
ensure_token() {
  [[ -z "$TOKEN" ]] && TOKEN="$(get_token)"
}

# --- Formatter (jq) ---

# Base format: url, title, full_text (first 4096 chars)
JQ_BASE='{url: .url, title: .title}'

JQ_ALL='
  {
    full_title: (if .breadcrumbs then (.breadcrumbs | map(.name) | join(" / ")) else null end),
    snippet: (if .passages then (.passages[0] // .description) else null end),
    url: .url,
    title: .title
  } | with_entries(select(.value != null and .value != ""))
'

JQ_TRACKER='
  {
    ticket_id: .id,
    resolution: .resolution,
    author_name: .author.name,
    author_login: .author.login,
    url: .url,
    title: .title
  } | with_entries(select(.value != null and .value != ""))
'

JQ_STACKOVERFLOW='
  {
    question: .description,
    answer: .best_answer.text,
    url: .url,
    title: .title
  } | with_entries(select(.value != null and .value != ""))
'

JQ_SEMANTIC_CODE='
  {
    description: .description,
    code: .original_content,
    url: .url,
    title: .title
  } | with_entries(select(.value != null and .value != ""))
'

# --- API call ---
do_search() {
  local layer="$1"
  local query="$2"
  local page_size="${3:-10}"
  local doc_facet_product="${4:-}"
  local jq_fmt="$5"

  ensure_token

  local params="text=$(printf '%s' "$query" | jq -sRr @uri)"
  params+="&layers=${layer}"
  params+="&version=2"
  params+="&${layer}.per_page=${page_size}"
  params+="&codeassistant=0"

  if [[ -n "$doc_facet_product" ]]; then
    params+="&doc.facet.product=$(printf '%s' "$doc_facet_product" | jq -sRr @uri)"
  fi

  local response
  response=$(curl -sf -H "Authorization: OAuth $TOKEN" "${BASE_URL}?${params}")

  if [[ -z "$response" ]]; then
    echo "ERROR: Empty response from API" >&2
    return 1
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$response"
    return
  fi

  # Extract results from all verticals, format each document
  echo "$response" | jq --argjson dummy 0 "
    [to_entries[].value.result // [] | .[] | ${jq_fmt}]
  "
}

# --- Commands ---

cmd_search() {
  local query="" page_size=10 doc_facet_product=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --page-size)    page_size="$2"; shift 2 ;;
      --product)      doc_facet_product="$2"; shift 2 ;;
      *)              query="$1"; shift ;;
    esac
  done
  if [[ -z "$query" ]]; then echo "ERROR: query required" >&2; return 1; fi

  local layer="all"
  [[ -n "$doc_facet_product" ]] && layer="doc"
  do_search "$layer" "$query" "$page_size" "$doc_facet_product" "$JQ_ALL"
}

cmd_stsearch() {
  local query="" page_size=10
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --page-size)  page_size="$2"; shift 2 ;;
      *)            query="$1"; shift ;;
    esac
  done
  if [[ -z "$query" ]]; then echo "ERROR: query required" >&2; return 1; fi
  do_search "tracker" "$query" "$page_size" "" "$JQ_TRACKER"
}

cmd_sosearch() {
  local query="" page_size=10
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --page-size)  page_size="$2"; shift 2 ;;
      *)            query="$1"; shift ;;
    esac
  done
  if [[ -z "$query" ]]; then echo "ERROR: query required" >&2; return 1; fi
  do_search "stackoverflow" "$query" "$page_size" "" "$JQ_STACKOVERFLOW"
}

cmd_code_search() {
  local query="" page_size=10
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --page-size)  page_size="$2"; shift 2 ;;
      *)            query="$1"; shift ;;
    esac
  done
  if [[ -z "$query" ]]; then echo "ERROR: query required" >&2; return 1; fi
  do_search "semantic_code" "$query" "$page_size" "" "$JQ_SEMANTIC_CODE"
}

# --- Main ---
usage() {
  cat <<'EOF'
Usage: intrasearch-cli.sh <command> <query> [options]

Commands:
  search QUERY [--page-size N] [--product PRODUCT]   Wiki & docs search
  stsearch QUERY [--page-size N]                      Tracker search
  sosearch QUERY [--page-size N]                      Stack Overflow search
  code-search QUERY [--page-size N]                   Semantic code search

Operators (in query string):
  search:      url:"<url>*"
  stsearch:    url:"<url>*", s_assignee:"<login>", s_author:"<login>",
               s_created_at:"'<from>'..'<to>'" (YYYYMMDD), s_tags:"<tag>", s_queue:"<queue>"
  sosearch:    url:"<url>*", s_is_answered:"0/1", s_tags:"<tag>"
  code-search: url:"<url>*", s_type:"function|class", s_branch:"trunk",
               s_language:"C++|Python|Go|Java|Kotlin|TypeScript|Swift",
               s_project:"<path>"

Options:
  --page-size N    Results per page (1-50, default 10)
  --product NAME   Filter by doc product (search only)

Auth: INTRASEARCH_TOKEN env var or ~/.mcp_store/oauth_token
EOF
}

if [[ $# -eq 0 ]]; then
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
  search)       cmd_search "$@" ;;
  stsearch)     cmd_stsearch "$@" ;;
  sosearch)     cmd_sosearch "$@" ;;
  code-search)  cmd_code_search "$@" ;;
  help|--help|-h) usage ;;
  *)
    echo "Unknown command: $command" >&2
    usage
    exit 1
    ;;
esac
