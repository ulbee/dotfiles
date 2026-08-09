#!/bin/bash
set -euo pipefail

# Wiki CLI — wrapper around wiki-api.yandex-team.ru/api/v2/public
# Usage: wiki-cli.sh <command> <args>

get_token() {
  if [[ -n "${WIKI_TOKEN:-}" ]]; then
    echo "$WIKI_TOKEN"
  elif [[ -n "${INTRASEARCH_TOKEN:-}" ]]; then
    echo "$INTRASEARCH_TOKEN"
  elif [[ -f "$HOME/.mcp_store/oauth_token" ]]; then
    cat "$HOME/.mcp_store/oauth_token"
  else
    echo "ERROR: No OAuth token found." >&2
    echo "Set WIKI_TOKEN or save to ~/.mcp_store/oauth_token" >&2
    exit 1
  fi
}

TOKEN=""
JSON_OUTPUT="false"
ensure_token() {
  [[ -z "$TOKEN" ]] && TOKEN="$(get_token)"
}

WIKI_API="https://wiki-api.yandex-team.ru/api/v2/public"

# Extract slug from URL or use as-is
normalize_slug() {
  local input="$1"
  if [[ "$input" == http* ]]; then
    echo "$input" | sed 's|https\?://wiki\.yandex-team\.ru/||; s|/$||'
  else
    echo "$input" | sed 's|^/||; s|/$||'
  fi
}

cmd_read() {
  local slug max_chars=""
  slug=$(normalize_slug "$1")
  shift
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --max-chars) max_chars="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  ensure_token

  local response
  response=$(curl -sf \
    -H "Authorization: OAuth $TOKEN" \
    "${WIKI_API}/pages?slug=${slug}&fields=content,last_revision_id" 2>&1) || {
    echo "ERROR: Failed to fetch page '${slug}'" >&2
    echo "$response" >&2
    exit 1
  }

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$response" | jq --arg url "https://wiki.yandex-team.ru/${slug}" '{content: .content, url: $url}'
    return
  fi

  echo "$response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
content = data.get('content', '')
max_chars = ${max_chars:-0}
if max_chars > 0 and len(content) > max_chars:
    content = content[:max_chars] + '\n... (truncated, total ' + str(len(content)) + ' chars)'
print(content)
"
}

cmd_tree() {
  local slug
  slug=$(normalize_slug "$1")
  ensure_token

  local response
  response=$(curl -sf \
    -H "Authorization: OAuth $TOKEN" \
    "${WIKI_API}/pages/tree?slug=${slug}" 2>&1) || {
    echo "ERROR: Failed to fetch tree for '${slug}'" >&2
    exit 1
  }

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$response"
    return
  fi

  echo "$response" | python3 -c "
import json, sys

def print_tree(node, indent=0):
    prefix = '  ' * indent
    print(f\"{prefix}- {node['title']}\")
    print(f\"{prefix}  slug: {node['slug']}\")
    for child in node.get('children', []):
        print_tree(child, indent + 1)

data = json.load(sys.stdin)
print_tree(data['root'])
"
}

cmd_info() {
  local slug
  slug=$(normalize_slug "$1")
  ensure_token

  curl -sf \
    -H "Authorization: OAuth $TOKEN" \
    "${WIKI_API}/pages?slug=${slug}&fields=title,last_revision_id,authors" | \
    python3 -m json.tool
}

cmd_help() {
  cat <<HELP
Usage: wiki-cli.sh <command> <page-url-or-slug>

Commands:
  read <url|slug>   — Read page content (returns wiki markup)
  tree <url|slug>   — Get tree of subpages
  info <url|slug>   — Get page metadata

Examples:
  wiki-cli.sh read taxi/partnerproducts/pro/unit-tests/yxpro-unit-tests-article
  wiki-cli.sh read https://wiki.yandex-team.ru/taxi/partnerproducts/pro/unit-tests/yxpro-unit-tests-article
  wiki-cli.sh tree taxi/partnerproducts/pro/unit-tests

Auth: WIKI_TOKEN env var, INTRASEARCH_TOKEN, or ~/.mcp_store/oauth_token
HELP
}

# Parse global flags
args=()
for arg in "$@"; do
  [[ "$arg" == "--json" ]] && JSON_OUTPUT="true" || args+=("$arg")
done
set -- "${args[@]+"${args[@]}"}"

CMD="${1:-help}"
shift || true
case "$CMD" in
  read)    cmd_read "${1:?Missing page URL or slug}" "${@:2}" ;;
  tree)    cmd_tree "${1:?Missing page URL or slug}" ;;
  info)    cmd_info "${1:?Missing page URL or slug}" ;;
  help|-h|--help) cmd_help ;;
  *)       echo "Unknown command: $CMD" >&2; cmd_help; exit 1 ;;
esac
