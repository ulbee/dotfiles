#!/usr/bin/env bash
set -euo pipefail

# Docs CLI — read docs.yandex-team.ru pages with OAuth

get_token() {
  if [[ -n "${DOCS_TOKEN:-}" ]]; then
    echo "$DOCS_TOKEN"
  elif [[ -f "$HOME/.mcp_store/oauth_token" ]]; then
    cat "$HOME/.mcp_store/oauth_token"
  else
    echo "ERROR: No token found." >&2
    exit 1
  fi
}

TOKEN=""
JSON_OUTPUT="false"

auth_header() {
  [[ -z "$TOKEN" ]] && TOKEN="$(get_token)"
  echo "Authorization: OAuth $TOKEN"
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

# Parse global flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) JSON_OUTPUT="true"; shift ;;
    *) break ;;
  esac
done

CMD="${1:-help}"
shift || true

# Strip --json from remaining args
args=()
for arg in "$@"; do
  [[ "$arg" == "--json" ]] && JSON_OUTPUT="true" || args+=("$arg")
done
set -- "${args[@]+"${args[@]}"}"

case "$CMD" in
  read)
    [[ $# -lt 1 ]] && { cli_error "invalid_argument" "URL or path required" "docs-cli.sh read <url-or-path>"; exit 1; }
    URL="$1"
    if [[ "$URL" != http* ]]; then
      URL="https://docs.yandex-team.ru/$URL"
    fi
    HTML=$(curl -sf "$URL" -H "$(auth_header)" -L)
    CONTENT=$(echo "$HTML" | python3 -c "
import sys, re, html

content = sys.stdin.read()

for pattern in [r'<article[^>]*>(.*?)</article>', r'<main[^>]*>(.*?)</main>', r'<div class=\"dc-doc-page__content\"[^>]*>(.*?)</div>']:
    match = re.search(pattern, content, re.DOTALL)
    if match:
        content = match.group(1)
        break

content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
content = re.sub(r'<[^>]+>', ' ', content)
content = html.unescape(content)
content = re.sub(r'\s+', ' ', content).strip()
content = re.sub(r' ([A-ZА-ЯЁ])', r'\n\1', content)

print(content[:10000])
")
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      jq -n --arg content "$CONTENT" --arg url "$URL" '{content: $content, url: $url}'
    else
      echo "$CONTENT"
    fi
    ;;
  help|--help|-h)
    cat <<'EOF'
Usage: docs-cli.sh [--json] <command> [args]

Commands:
  read <url-or-path>    Read a docs page (first 10000 chars)

Global flags:
  --json    Structured JSON output {content, url}

Auth: DOCS_TOKEN env var or ~/.mcp_store/oauth_token
EOF
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    exit 1
    ;;
esac
