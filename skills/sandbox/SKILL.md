---
name: sandbox
description: "Search Sandbox tasks for PRs, view logs, analyze CI errors, access artifacts"
allowed-tools: Bash(scripts/sandbox-cli.sh:*)
user-invocable: false
---
CLI: `sandbox-cli.sh <command> [args]`

Commands:
  tasks PR_ID [ACTION_FILTER]           List Sandbox tasks for a PR
  task-info TASK_ID                     Task metadata (status, job, action, logs URL)
  log TASK_ID [LOG_FILE]                Task logs (default: errors from execution.log)
  errors TASK_ID                        Smart error analysis (tests, format, build)
  failed PR_ID                          All failed tasks + error analysis
  search-log TASK_ID PATTERN [CTX]      Grep execution.log (default ctx: 3 lines)
  artifact TASK_ID [TYPE] [FILE]        Access artifacts (TASK_LOGS, TEAMCITY_ARTIFACTS)

Auth: CI_OAUTH_TOKEN env var or ~/.ci/token
