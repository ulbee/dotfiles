#!/usr/bin/env bash
set -euo pipefail

# Experiments3 CLI — wrapper over tariff-editor experiments3 API

PROD_BASE="https://tariff-editor.taxi.yandex-team.ru/api/admin/taxi_exp"
TST_BASE="https://tariff-editor.taxi.tst.yandex-team.ru/api-t/admin/taxi_exp"

# --- Auth ---
get_token() {
  if [[ -n "${EXPERIMENTS3_TOKEN:-}" ]]; then
    echo "$EXPERIMENTS3_TOKEN"
  elif [[ -f "$HOME/.mcp_store/oauth_token" ]]; then
    cat "$HOME/.mcp_store/oauth_token"
  else
    echo "ERROR: No token found." >&2
    echo "Set EXPERIMENTS3_TOKEN or save token to ~/.mcp_store/oauth_token" >&2
    echo "Get token: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=ed682c8c3e9c489cb0734062fc675a3d" >&2
    exit 1
  fi
}

TOKEN=""
JSON_OUTPUT="false"
auth_header() {
  [[ -z "$TOKEN" ]] && TOKEN="$(get_token)"
  echo "Authorization: OAuth $TOKEN"
}

# --- Env ---
BASE_URL="$PROD_BASE"
NAMESPACE=""

parse_env() {
  for arg in "$@"; do
    case "$arg" in
      --tst|--testing) BASE_URL="$TST_BASE" ;;
      --namespace=*) NAMESPACE="${arg#*=}" ;;
      --json) JSON_OUTPUT="true" ;;
    esac
  done
}

ns_param() {
  if [[ -n "$NAMESPACE" ]]; then
    echo "&tplatform_namespace=$NAMESPACE"
  fi
}

# --- Commands ---

get_config() {
  local name="$1"
  curl -sf "$BASE_URL/v1/configs/?name=$name" -H "$(auth_header)"
}

get_experiment() {
  local name="$1"
  curl -sf "$BASE_URL/v1/experiments/?name=$name" -H "$(auth_header)"
}

search_configs() {
  local query="$BASE_URL/v1/configs/list?limit=${1:-10}&offset=${2:-0}"
  shift 2 2>/dev/null || true
  # Append remaining args as query params
  for arg in "$@"; do
    case "$arg" in
      --consumer=*) query+="&consumer=${arg#*=}" ;;
      --name=*) query+="&name=${arg#*=}" ;;
      --owner=*) query+="&owner=${arg#*=}" ;;
    esac
  done
  curl -sf "$query" -H "$(auth_header)"
}

search_experiments() {
  local query="$BASE_URL/v1/experiments/list/?limit=${1:-10}&offset=${2:-0}"
  shift 2 2>/dev/null || true
  for arg in "$@"; do
    case "$arg" in
      --consumer=*) query+="&consumer=${arg#*=}" ;;
      --name=*) query+="&name=${arg#*=}" ;;
      --owner=*) query+="&owner=${arg#*=}" ;;
    esac
  done
  curl -sf "$query" -H "$(auth_header)"
}

draft_update_config() {
  local name="$1"
  local last_modified_at="$2"
  local body="$3"
  curl -sf -X POST "$BASE_URL/v1/configs/drafts/for-update/?name=$name&last_modified_at=$last_modified_at" \
    -H "$(auth_header)" \
    -H "Content-Type: application/json" \
    -d "{\"run_manually\": false, \"data\": $body, \"tickets\": {}}"
}

draft_update_experiment() {
  local name="$1"
  local last_modified_at="$2"
  local body="$3"
  curl -sf -X POST "$BASE_URL/v1/experiments/drafts/for-update/?name=$name&last_modified_at=$last_modified_at" \
    -H "$(auth_header)" \
    -H "Content-Type: application/json" \
    -d "{\"run_manually\": false, \"data\": $body, \"tickets\": {}}"
}

schema_draft_create() {
  local type="$1"  # experiment_name or config_name
  local name="$2"
  local schema_body="$3"
  local skip_validating="${4:-false}"
  local default_value="${5:-}"
  local body
  body="{\"schema_body\": $(echo "$schema_body" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))'), \"skip_validating_values\": $skip_validating"
  if [[ -n "$default_value" ]]; then
    body+=", \"default_value\": $(echo "$default_value" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')"
  fi
  body+="}"
  local response http_code
  response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/v1/schemas/draft?${type}=${name}$(ns_param)" \
    -H "$(auth_header)" \
    -H "Content-Type: application/json" \
    -d "$body")
  http_code=$(echo "$response" | tail -1)
  body_out=$(echo "$response" | sed '$d')
  if [[ "$http_code" == "409" ]]; then
    echo "CONFLICT: Draft already exists for ${name}." >&2
    echo "$body_out"
    exit 1
  elif [[ "$http_code" -ge 400 ]]; then
    echo "ERROR (HTTP $http_code):" >&2
    echo "$body_out" >&2
    exit 1
  fi
  echo "$body_out"
}

schema_draft_get() {
  local param="$1"  # experiment_name=X, config_name=X, or draft_id=X
  curl -sf "$BASE_URL/v1/schemas/draft?${param}$(ns_param)" \
    -H "$(auth_header)"
}

schema_draft_delete() {
  local param="$1"
  curl -sf -X DELETE "$BASE_URL/v1/schemas/draft?${param}$(ns_param)" \
    -H "$(auth_header)"
}

schema_publish() {
  local draft_id="$1"
  local response http_code body_out
  response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/v1/schemas/publish?draft_id=${draft_id}$(ns_param)" \
    -H "$(auth_header)")
  http_code=$(echo "$response" | tail -1)
  body_out=$(echo "$response" | sed '$d')
  if [[ "$http_code" -ge 400 ]]; then
    echo "ERROR (HTTP $http_code):" >&2
    echo "$body_out" >&2
    exit 1
  fi
  echo "$body_out"
}

# --- Main ---
parse_env "$@"

# Remove global flags from args
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --tst|--testing|--namespace=*|--json) ;;
    *) ARGS+=("$arg") ;;
  esac
done
set -- "${ARGS[@]}"

CMD="${1:-help}"
shift || true

case "$CMD" in
  config)
    [[ $# -lt 1 ]] && { echo "Usage: experiments3-cli.sh config <name> [--tst]"; exit 1; }
    get_config "$1"
    ;;
  experiment)
    [[ $# -lt 1 ]] && { echo "Usage: experiments3-cli.sh experiment <name> [--tst]"; exit 1; }
    get_experiment "$1"
    ;;
  search-configs)
    search_configs "$@"
    ;;
  search-experiments)
    search_experiments "$@"
    ;;
  draft-config)
    [[ $# -lt 3 ]] && { echo "Usage: experiments3-cli.sh draft-config <name> <last_modified_at> '<json_body>' [--tst]"; exit 1; }
    draft_update_config "$1" "$2" "$3"
    ;;
  draft-experiment)
    [[ $# -lt 3 ]] && { echo "Usage: experiments3-cli.sh draft-experiment <name> <last_modified_at> '<json_body>' [--tst]"; exit 1; }
    draft_update_experiment "$1" "$2" "$3"
    ;;
  schema-draft-create)
    [[ $# -lt 3 ]] && { echo "Usage: experiments3-cli.sh schema-draft-create <config_name|experiment_name> <name> <schema_body_file_or_string> [skip_validating] [--default-value=<json>] [--default-value-file=<path>]"; exit 1; }
    TYPE="$1"
    NAME="$2"
    if [[ -f "$3" ]]; then
      SCHEMA_BODY=$(cat "$3")
    else
      SCHEMA_BODY="$3"
    fi
    SKIP="${4:-false}"
    DEFAULT_VALUE=""
    for a in "$@"; do
      case "$a" in
        --default-value=*) DEFAULT_VALUE="${a#*=}" ;;
        --default-value-file=*) DEFAULT_VALUE=$(cat "${a#*=}") ;;
      esac
    done
    schema_draft_create "$TYPE" "$NAME" "$SCHEMA_BODY" "$SKIP" "$DEFAULT_VALUE"
    ;;
  schema-draft-get)
    [[ $# -lt 1 ]] && { echo "Usage: experiments3-cli.sh schema-draft-get <config_name=X|experiment_name=X|draft_id=X>"; exit 1; }
    schema_draft_get "$1"
    ;;
  schema-draft-delete)
    [[ $# -lt 1 ]] && { echo "Usage: experiments3-cli.sh schema-draft-delete <config_name=X|experiment_name=X|draft_id=X>"; exit 1; }
    schema_draft_delete "$1"
    ;;
  schema-publish)
    [[ $# -lt 1 ]] && { echo "Usage: experiments3-cli.sh schema-publish <draft_id>"; exit 1; }
    schema_publish "$1"
    ;;
  help|--help|-h)
    cat <<'EOF'
Experiments3 CLI — tariff-editor experiments3 API

Commands:
  config <name>                Get config by exact name
  experiment <name>            Get experiment by exact name
  search-configs [limit] [offset] [--name=X] [--consumer=X] [--owner=X]
                               Search configs with filters
  search-experiments [limit] [offset] [--name=X] [--consumer=X] [--owner=X]
                               Search experiments with filters
  draft-config <name> <last_modified_at> '<json_body>'
                               Create a draft for config update (needs approval)
  draft-experiment <name> <last_modified_at> '<json_body>'
                               Create a draft for experiment update (needs approval)
  schema-draft-create <config_name|experiment_name> <name> <schema_yaml_file_or_string> [skip_validating]
                               [--default-value='<json>'] [--default-value-file=<path>]
                               Create a schema draft. Returns draft_id on success.
                               409 if draft already exists (returns existing draft_id).
  schema-draft-get <config_name=X|experiment_name=X|draft_id=X>
                               Get a schema draft
  schema-draft-delete <config_name=X|experiment_name=X|draft_id=X>
                               Delete a schema draft
  schema-publish <draft_id>    Publish a schema draft. Config/experiment must exist.

Options:
  --tst, --testing       Use testing environment
  --namespace=X          Set tplatform_namespace for platform admin experiments

Auth:
  Token from: EXPERIMENTS3_TOKEN env var or ~/.mcp_store/oauth_token
  Get token: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=ed682c8c3e9c489cb0734062fc675a3d
EOF
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    echo "Run with 'help' for usage" >&2
    exit 1
    ;;
esac
