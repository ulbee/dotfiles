---
name: ci-releases
allowed-tools: Bash(scripts/ci-releases-cli.sh:*)
description: List, start, and inspect CI releases and run custom builds via Arcadia CI gRPC API
---
CLI: `ci-releases-cli.sh <command> <args>`

Commands:
  list CONFIG_PATH RELEASE_ID [LIMIT]         List recent releases
  changelog CONFIG_PATH RELEASE_ID NUMBER     Release changelog (commits, issues)
  start CONFIG_PATH RELEASE_ID [REASON]       Start new release
  free-commits CONFIG_PATH RELEASE_ID [LIMIT] Unreleased commits
  run-custom CONFIG_PATH [ACTION_ID] [BRANCH] [FLOW_VARS_JSON]  Custom build

Arguments:
  CONFIG_PATH — path to a.yaml (e.g. taxi/uservices/services/my-svc/a.yaml)
  RELEASE_ID  — usually "release" (check ci.releases: in a.yaml)
  ACTION_ID   — action name from a.yaml (default: run_custom, often run-custom)
  FLOW_VARS   — JSON: {"units-checklist": {"unit": true}, "sanitize": "none"}

Global: --json for structured output. Run `help <cmd>` for details.
Auth: CI_OAUTH_TOKEN env var or ~/.ci_token
Requires: pip3 install grpcio grpcio-tools
