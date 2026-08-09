#!/usr/bin/env bash
set -euo pipefail

# CI Releases CLI — wrapper over Arcadia CI gRPC API
# Manages releases: list, start, changelog, rollback

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROTO_DIR="${PROTO_DIR:-/tmp/ci_proto_compiled}"
ARC_ROOT="${ARC_ROOT:-$(arc root 2>/dev/null || echo /codenv/arcadia_2)}"
CA_CERT="/etc/ssl/certs/ca-certificates.crt"

# --- Auth ---
get_token() {
  if [[ -n "${CI_OAUTH_TOKEN:-}" ]]; then
    echo "$CI_OAUTH_TOKEN"
  elif [[ -f "$HOME/.ci_token" ]]; then
    cat "$HOME/.ci_token"
  else
    echo "ERROR: No CI token found." >&2
    echo "Set CI_OAUTH_TOKEN or save token to ~/.ci_token" >&2
    echo "Get token: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=5c2eb9ec7cc74dcd960f400ff32b7b38" >&2
    exit 1
  fi
}

# --- Compile proto if needed ---
ensure_proto() {
  if [[ -f "$PROTO_DIR/ci/proto/public/ci/release_pb2.py" ]]; then
    return
  fi
  mkdir -p "$PROTO_DIR"
  python3 -m grpc_tools.protoc \
    --proto_path="$ARC_ROOT" \
    --python_out="$PROTO_DIR" \
    --grpc_python_out="$PROTO_DIR" \
    ci/proto/public/ci/release.proto \
    ci/proto/public/ci/action.proto \
    ci/proto/public/ci/job_launch.proto \
    ci/proto/public/ci/public_api_common.proto \
    ci/proto/public/mcp/mcp_releases.proto
}

JSON_OUTPUT="false"

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

# --- Main ---
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
  list)
    CONFIG_PATH="${1:?Usage: ci-releases-cli.sh list <config_path> <release_id> [limit]}"
    RELEASE_ID="${2:?Usage: ci-releases-cli.sh list <config_path> <release_id> [limit]}"
    LIMIT="${3:-10}"
    ensure_proto
    TOKEN="$(get_token)"
    python3 -c "
import sys
sys.path.insert(0, '$PROTO_DIR')
import grpc, json
from google.protobuf.json_format import MessageToDict
from ci.proto.public.ci import release_pb2, release_pb2_grpc, public_api_common_pb2

with open('$CA_CERT', 'rb') as f:
    creds = grpc.ssl_channel_credentials(root_certificates=f.read())
channel = grpc.secure_channel('ci-public-api.yandex-team.ru:9091', creds)
stub = release_pb2_grpc.ReleaseServiceStub(channel)

request = release_pb2.ListReleasesRequest(
    release_identifier=public_api_common_pb2.ReleaseProcessId(
        config_path='$CONFIG_PATH',
        release_id='$RELEASE_ID',
    ),
    limit=$LIMIT,
)
metadata = [('authorization', 'OAuth $TOKEN')]
response = stub.ListReleases(request, metadata=metadata)

releases = []
for r in response.releases:
    d = MessageToDict(r)
    rel = d.get('release', {})
    releases.append({
        'number': rel.get('launchNumber'),
        'version': rel.get('version', {}).get('full'),
        'status': rel.get('status'),
        'created': rel.get('created'),
        'link': f'https://a.yandex-team.ru/projects/{\"$CONFIG_PATH\".split(\"/\")[0]}/ci/releases/overview?dir={\"$CONFIG_PATH\".rsplit(\"/\", 1)[0]}&id=$RELEASE_ID&version={rel.get(\"version\", {}).get(\"full\", \"\")}'
    })
print(json.dumps(releases, indent=2, ensure_ascii=False))
"
    ;;
  changelog)
    CONFIG_PATH="${1:?Usage: ci-releases-cli.sh changelog <config_path> <release_id> <launch_number>}"
    RELEASE_ID="${2:?}"
    LAUNCH_NUMBER="${3:?}"
    ensure_proto
    TOKEN="$(get_token)"
    python3 -c "
import sys
sys.path.insert(0, '$PROTO_DIR')
import grpc, json
from google.protobuf.json_format import MessageToDict
from ci.proto.public.ci import release_pb2, release_pb2_grpc, public_api_common_pb2

with open('$CA_CERT', 'rb') as f:
    creds = grpc.ssl_channel_credentials(root_certificates=f.read())
channel = grpc.secure_channel('ci-public-api.yandex-team.ru:9091', creds)
stub = release_pb2_grpc.ReleaseServiceStub(channel)

request = release_pb2.GetChangelogRequest(
    release_identifier=public_api_common_pb2.ReleaseProcessId(
        config_path='$CONFIG_PATH',
        release_id='$RELEASE_ID',
    ),
    launch_number=$LAUNCH_NUMBER,
)
metadata = [('authorization', 'OAuth $TOKEN')]
response = stub.GetChangelog(request, metadata=metadata)

changes = [MessageToDict(c) for c in response.changelog]
print(json.dumps(changes, indent=2, ensure_ascii=False))
"
    ;;
  start)
    CONFIG_PATH="${1:?Usage: ci-releases-cli.sh start <config_path> <release_id> [reason] [flow_vars_json]}"
    RELEASE_ID="${2:?}"
    REASON="${3:-Started via CLI}"
    FLOW_VARS="${4:-}"
    ensure_proto
    TOKEN="$(get_token)"
    python3 -c "
import sys
sys.path.insert(0, '$PROTO_DIR')
import grpc, json
from google.protobuf.json_format import MessageToDict
from ci.proto.public.ci import release_pb2, release_pb2_grpc, public_api_common_pb2

with open('$CA_CERT', 'rb') as f:
    creds = grpc.ssl_channel_credentials(root_certificates=f.read())
channel = grpc.secure_channel('ci-public-api.yandex-team.ru:9091', creds)
stub = release_pb2_grpc.ReleaseServiceStub(channel)

request = release_pb2.StartReleaseRequest(
    release_identifier=public_api_common_pb2.ReleaseProcessId(
        config_path='$CONFIG_PATH',
        release_id='$RELEASE_ID',
    ),
    launch_reason='$REASON',
)

flow_vars = '$FLOW_VARS'
if flow_vars:
    request.flow_vars.CopyFrom(public_api_common_pb2.FlowVars(json=flow_vars))

token = '$TOKEN'
metadata = [('authorization', f'OAuth {token}')]
response = stub.StartRelease(request, metadata=metadata)
d = MessageToDict(response)
print(json.dumps(d, indent=2, ensure_ascii=False))
"
    ;;
  free-commits)
    CONFIG_PATH="${1:?Usage: ci-releases-cli.sh free-commits <config_path> <release_id> [limit]}"
    RELEASE_ID="${2:?}"
    LIMIT="${3:-20}"
    ensure_proto
    TOKEN="$(get_token)"
    python3 -c "
import sys
sys.path.insert(0, '$PROTO_DIR')
import grpc, json
from google.protobuf.json_format import MessageToDict
from ci.proto.public.ci import release_pb2, release_pb2_grpc, public_api_common_pb2

with open('$CA_CERT', 'rb') as f:
    creds = grpc.ssl_channel_credentials(root_certificates=f.read())
channel = grpc.secure_channel('ci-public-api.yandex-team.ru:9091', creds)
stub = release_pb2_grpc.ReleaseServiceStub(channel)

request = release_pb2.GetFreeCommitsRequest(
    release_identifier=public_api_common_pb2.ReleaseProcessId(
        config_path='$CONFIG_PATH',
        release_id='$RELEASE_ID',
    ),
    limit=$LIMIT,
)
metadata = [('authorization', 'OAuth $TOKEN')]
response = stub.GetFreeCommits(request, metadata=metadata)
commits = [MessageToDict(c) for c in response.commits]
print(json.dumps(commits, indent=2, ensure_ascii=False))
"
    ;;
  trigger)
    CONFIG_PATH="${1:?Usage: ci-releases-cli.sh trigger <config_path> <release_id> <launch_number> <stage>}"
    RELEASE_ID="${2:?}"
    LAUNCH_NUMBER="${3:?}"
    STAGE="${4:?Stage required: prestable or stable}"
    JOB_ID="stage-trigger-${STAGE}"
    ensure_proto
    TOKEN="$(get_token)"
    python3 -c "
import sys
sys.path.insert(0, '$PROTO_DIR')
import grpc, json
from google.protobuf.json_format import MessageToDict
from ci.proto.public.ci import job_launch_pb2, job_launch_pb2_grpc, public_api_common_pb2

with open('$CA_CERT', 'rb') as f:
    creds = grpc.ssl_channel_credentials(root_certificates=f.read())
channel = grpc.secure_channel('ci-public-api.yandex-team.ru:9091', creds)
stub = job_launch_pb2_grpc.JobLaunchServiceStub(channel)

launch_id = public_api_common_pb2.LaunchId(
    release_process_id=public_api_common_pb2.ReleaseProcessId(
        config_path='$CONFIG_PATH',
        release_id='$RELEASE_ID',
    ),
    launch_number=$LAUNCH_NUMBER,
)
request = job_launch_pb2.EnableManualTriggerRequest(
    launch_job_id=public_api_common_pb2.LaunchJobId(
        launch_id=launch_id,
        job_id='$JOB_ID',
    ),
)

token = '$TOKEN'
metadata = [('authorization', f'OAuth {token}')]
try:
    response = stub.EnableManualTrigger(request, metadata=metadata)
except grpc.RpcError as e:
    print(json.dumps({'error': e.details(), 'code': str(e.code())}, indent=2))
    sys.exit(1)
d = MessageToDict(response)
print(json.dumps(d, indent=2, ensure_ascii=False))
"
    ;;
  run-custom)
    CONFIG_PATH="${1:?Usage: ci-releases-cli.sh run-custom <config_path> [action_id] [branch] [flow_vars_json]}"
    ACTION_ID="${2:-run-custom}"
    BRANCH="${3:-}"
    FLOW_VARS="${4:-}"
    ensure_proto
    TOKEN="$(get_token)"
    python3 -c "
import sys
sys.path.insert(0, '$PROTO_DIR')
import grpc, json
from google.protobuf.json_format import MessageToDict
from ci.proto.public.ci import action_pb2, action_pb2_grpc, public_api_common_pb2

with open('$CA_CERT', 'rb') as f:
    creds = grpc.ssl_channel_credentials(root_certificates=f.read())
channel = grpc.secure_channel('ci-public-api.yandex-team.ru:9091', creds)
stub = action_pb2_grpc.ActionServiceStub(channel)

request = action_pb2.StartActionRequest(
    action_identifier=public_api_common_pb2.ActionProcessId(
        config_path='$CONFIG_PATH',
        action_id='$ACTION_ID',
    ),
)

branch = '$BRANCH'
if branch:
    request.target_revision.CopyFrom(public_api_common_pb2.CommitReference(branch=branch))

flow_vars = '$FLOW_VARS'
if flow_vars:
    request.flow_vars.CopyFrom(public_api_common_pb2.FlowVars(json=flow_vars))

token = '$TOKEN'
metadata = [('authorization', f'OAuth {token}')]
response = stub.StartAction(request, metadata=metadata)
d = MessageToDict(response)
print(json.dumps(d, indent=2, ensure_ascii=False))
"
    ;;
  help|--help|-h)
    if [[ $# -gt 0 ]]; then
      case "$1" in
        list) echo "list CONFIG_PATH RELEASE_ID [LIMIT]"; echo "  List recent releases. Example: ci-releases-cli.sh list svc/a.yaml release 5" ;;
        run-custom) echo "run-custom CONFIG_PATH [ACTION_ID] [BRANCH] [FLOW_VARS_JSON]"; echo "  Run custom build. ACTION_ID defaults to run_custom." ;;
        *) echo "No detailed help for '$1'." ;;
      esac
    else
      cat <<'EOF'
Usage: ci-releases-cli.sh [--json] <command> <args>

Commands:
  list CONFIG_PATH RELEASE_ID [LIMIT]          Recent releases
  changelog CONFIG_PATH RELEASE_ID NUMBER      Release changelog
  start CONFIG_PATH RELEASE_ID [REASON]        Start release
  free-commits CONFIG_PATH RELEASE_ID [LIMIT]  Unreleased commits
  run-custom CONFIG_PATH [ACTION_ID] [BRANCH] [FLOW_VARS]  Custom build

Global flags:
  --json    All commands already output JSON by default

Auth: CI_OAUTH_TOKEN env var or ~/.ci_token
Run 'help <command>' for details.
EOF
    fi
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    exit 1
    ;;
esac
