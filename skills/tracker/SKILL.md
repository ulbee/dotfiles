---
name: tracker
description: "Look up, search, create, update, and comment on Yandex Tracker tickets. Manage projects. Use when you need ticket details, status changes, issue search, or project management."
allowed-tools: Bash(scripts/tracker-cli.sh:*)
user-invocable: false
---
CLI: `scripts/tracker-cli.sh [--json] <command> [args]`

Commands:
  my-tasks [--queue QUEUE]                 My open tasks
  show TICKET [--fields F1,F2] [--compact]  Ticket details (--compact: brief)
  search --query "TQL" [--fields F1,F2]    Search (TQL)
  status TICKET STATUS [--field K=V]       Change status
  transitions TICKET                       Available transitions
  create --queue Q --summary S [--type T] [--description D] [--priority P]
  update TICKET --field K=V                Update fields (tags=+tag / tags=-tag)
  comment TICKET --text TEXT [--summonees u1,u2]
  links TICKET                             Show links
  link TICKET --to OTHER --type TYPE       Create link
  changelog TICKET [--field F --last N]    Change history
  comments TICKET [--order asc|desc]       List comments
  pr-id TICKET                             Get Arcanum PR ID
  clone-meta FROM TO [--skip f1,f2]        Copy metadata
  projects / project-show / project-create / project-update

Global: --json for structured JSON output. Run `help <cmd>` for details.
Auth: ~/.tracker-token or TRACKER_OAUTH_TOKEN
Get token: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=5f671d781aca402ab7460fde4050267b
