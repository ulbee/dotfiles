---
name: intrasearch
description: "Search internal wiki, documentation, Tracker issues, Stack Overflow, and monorepo code by semantic description. Use for any internal knowledge lookup."
allowed-tools: Bash(scripts/intrasearch-cli.sh:*)
user-invocable: true
---
CLI: `intrasearch-cli.sh <command> <query> [options]`

Commands:
  search QUERY [--page-size N] [--product NAME] [--max-chars N]  Wiki & docs
  stsearch QUERY [--page-size N]                    Tracker issues
  sosearch QUERY [--page-size N]                    Stack Overflow
  code-search QUERY [--page-size N]                 Monorepo code

Default: 5 results. Use --page-size 3 for brief, --max-chars to limit output.

Search operators: url:"<url>*", s_queue:"Q", s_assignee:"login", s_language:"Go", s_project:"path"
Auth: ~/.mcp_store/oauth_token or INTRASEARCH_TOKEN
