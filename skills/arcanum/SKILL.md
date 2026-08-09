---
name: arcanum
description: "View PR metadata, diffs, changed files, post review comments, reply, and resolve issues on Arcanum pull requests."
allowed-tools: Bash(scripts/arcanum-cli.sh:*)
user-invocable: false
---
CLI: `arcanum-cli.sh [--json] <command> [args]`

Commands:
  pr-status PR_ID                          Quick status
  pr-data PR_ID                            Metadata + all comments
  changed-files PR_ID                      List changed files
  file-diff PR_ID PATH                     Single file diff
  full-diff PR_ID [MAX_FILES]              All files diff in one call (for code review)
  file-content PR_ID PATH                  File at PR head
  checks PR_ID [--failed|--required|--pending|--active]  CI checks
  check-log PR_ID CHECK_TYPE               Check details + CI flow
  ci-jobs PR_ID [CHECK_TYPE]               Sandbox tasks
  ci-errors TASK_ID                        Smart error analysis
  ci-failed PR_ID                          All failed tasks + errors
  open-issues PR_ID                        Open review issues
  post-comment PR_ID --content TEXT [--file PATH --line N]
  reply COMMENT_ID --content TEXT
  close-issue COMMENT_ID                   Resolve issue
  delete-comment PR_ID COMMENT_ID
  publish-drafts PR_ID
  diff-comments PR_ID                      Inline diff comments
  labels PR_ID [--add|--remove|--set LABEL]
  run-action PR_ID CHECK_TYPE              Trigger CI action
  deploy-testing PR_ID SERVICE             Label + trigger deploy
  worktree-create NAME|PR_ID [PATH]        Mount worktree
  worktree-remove PATH
  worktree-list [--status]

Global: --json for structured JSON output. Run `help <cmd>` for details.
Auth: ~/.arc/token or ARC_OAUTH_TOKEN
