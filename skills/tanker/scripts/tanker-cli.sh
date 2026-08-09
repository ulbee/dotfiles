#!/usr/bin/env bash
set -euo pipefail

# Tanker CLI — wrapper over Tanker REST API (New API v1)
# https://tanker.yandex-team.ru/api/v1/

BASE_URL="https://tanker.yandex-team.ru/api"

# --- Auth ---
get_token() {
  if [[ -n "${TANKER_API_TOKEN:-}" ]]; then
    echo "$TANKER_API_TOKEN"
  elif [[ -f "$HOME/.tanker_token" ]]; then
    cat "$HOME/.tanker_token"
  elif [[ -f "$HOME/.mcp_store/oauth_token" ]]; then
    cat "$HOME/.mcp_store/oauth_token"
  else
    echo "ERROR: No Tanker token found." >&2
    echo "Set TANKER_API_TOKEN env var or save token to ~/.tanker_token" >&2
    echo "Get token: https://nda.ya.ru/3SjQY7" >&2
    exit 1
  fi
}

TOKEN=""
auth_header() {
  [[ -z "$TOKEN" ]] && TOKEN="$(get_token)"
  echo "Authorization: OAuth $TOKEN"
}

# --- API helpers ---
api_get() {
  local url="$1"
  curl -sf -H "$(auth_header)" -H "Content-Type: application/json" "$url"
}

api_post() {
  local url="$1"
  local body="${2:-}"
  if [[ -n "$body" ]]; then
    curl -sf -X POST -H "$(auth_header)" -H "Content-Type: application/json" -d "$body" "$url"
  else
    curl -sf -X POST -H "$(auth_header)" -H "Content-Type: application/json" "$url"
  fi
}

api_post_file() {
  local url="$1"
  local file="$2"
  curl -sf -X POST -H "$(auth_header)" -H "Content-Type: application/json" -d "@$file" "$url"
}

api_patch() {
  local url="$1"
  local body="$2"
  curl -sf -X PATCH -H "$(auth_header)" -H "Content-Type: application/json" -d "$body" "$url"
}

api_delete() {
  local url="$1"
  curl -s -o /dev/null -w "%{http_code}" -X DELETE -H "$(auth_header)" "$url"
}

# --- URL encoding ---
urlencode() {
  python3 -c "import urllib.parse; print(urllib.parse.quote('$1', safe=''))"
}

# --- Commands ---

usage() {
  cat <<'USAGE'
Tanker CLI — manage translations via Tanker API

Usage: tanker-cli.sh <command> [args]

Commands:
  projects                                   List projects
  keysets <project>                           List keysets in project
  keys <project> <keyset> [--search PATTERN] [--limit N] [--branch BRANCH]
                                              List keys in keyset
  get-key <project> <keyset> <key> [--branch BRANCH]
                                              Get key with translations
  import <project> <keyset> <json-file> [--branch BRANCH] [--mode MODE]
                                              Import keys from JSON file
  update-key <project> <keyset> <key> <lang> <value> [--branch BRANCH]
                                              Update single key translation
  delete-key <project> <keyset> <key> [--branch BRANCH]
                                              Delete a key
  export <project> <keyset> [--branch BRANCH] [--format FORMAT] [--languages LANGS]
                                              Export keyset translations
USAGE
  exit 0
}

cmd_projects() {
  api_get "$BASE_URL/v1/project/" | jq -r '.items[] | "\(.code)\t\(.name)\t\(.status)"'
}

cmd_keysets() {
  local project="$1"
  local branch="${2:-master}"
  api_get "$BASE_URL/v1/project/$project/branch/$branch/keyset" \
    | jq -r '.items[] | "\(.code)\t\(.status)"'
}

cmd_keys() {
  local project="$1"
  local keyset="$2"
  shift 2

  local branch="master"
  local search=""
  local limit="50"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --branch) branch="$2"; shift 2 ;;
      --search) search="$2"; shift 2 ;;
      --limit) limit="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  local url="$BASE_URL/v1/project/$project/keyset/$keyset/branch/$branch/key?limit=$limit"
  if [[ -n "$search" ]]; then
    local encoded
    encoded=$(urlencode "$search")
    url="$url&name-gte=$encoded&name-lte=${encoded}~"
  fi

  api_get "$url" | jq -r '.items[] | .name as $name | (.translations.ru.payload.singular_form // "") as $ru | "\($name)\t\($ru)"'
}

cmd_get_key() {
  local project="$1"
  local keyset="$2"
  local key="$3"
  shift 3

  local branch="master"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --branch) branch="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  local encoded_key
  encoded_key=$(urlencode "$key")
  api_get "$BASE_URL/v1/project/$project/keyset/$keyset/branch/$branch/key/$encoded_key" | jq '.'
}

cmd_import() {
  local project="$1"
  local keyset="$2"
  local file="$3"
  shift 3

  local branch="master"
  local mode="CREATE_MISSING_KEYS"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --branch) branch="$2"; shift 2 ;;
      --mode) mode="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  api_post_file "$BASE_URL/v1/project/$project/keyset/$keyset/branch/$branch/import?mode=$mode" "$file" | jq '.'
}

cmd_update_key() {
  local project="$1"
  local keyset="$2"
  local key="$3"
  local lang="$4"
  local value="$5"
  shift 5

  local branch="master"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --branch) branch="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  local encoded_key
  encoded_key=$(urlencode "$key")
  local body
  body=$(jq -n --arg lang "$lang" --arg value "$value" '{
    translations: {
      ($lang): {
        language: $lang,
        status: "APPROVED",
        payload: { singular_form: $value }
      }
    }
  }')

  api_patch "$BASE_URL/v1/project/$project/keyset/$keyset/branch/$branch/key/$encoded_key" "$body" | jq '.'
}

cmd_delete_key() {
  local project="$1"
  local keyset="$2"
  local key="$3"
  shift 3

  local branch="master"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --branch) branch="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  local encoded_key
  encoded_key=$(urlencode "$key")
  local status
  status=$(api_delete "$BASE_URL/v1/project/$project/keyset/$keyset/branch/$branch/key/$encoded_key")
  if [[ "$status" == "204" ]]; then
    echo "Deleted: $key"
  else
    echo "Failed with HTTP $status"
    exit 1
  fi
}

cmd_export() {
  local project="$1"
  local keyset="$2"
  shift 2

  local branch="master"
  local format="json"
  local languages=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --branch) branch="$2"; shift 2 ;;
      --format) format="$2"; shift 2 ;;
      --languages) languages="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  local url="$BASE_URL/v1/project/$project/keyset/$keyset/branch/$branch/export?format=$format"
  if [[ -n "$languages" ]]; then
    url="$url&languages=$languages"
  fi

  api_get "$url" | jq '.'
}

# --- Main ---
[[ $# -eq 0 ]] && usage

cmd="$1"
shift

case "$cmd" in
  projects) cmd_projects ;;
  keysets) cmd_keysets "$@" ;;
  keys) cmd_keys "$@" ;;
  get-key) cmd_get_key "$@" ;;
  import) cmd_import "$@" ;;
  update-key) cmd_update_key "$@" ;;
  delete-key) cmd_delete_key "$@" ;;
  export) cmd_export "$@" ;;
  -h|--help|help) usage ;;
  *) echo "Unknown command: $cmd" >&2; usage ;;
esac
