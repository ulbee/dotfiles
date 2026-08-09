---
name: monium
description: "Search backend service logs via Monium gRPC API. Use when investigating backend errors, request logs, or service behavior."
allowed-tools: Bash(scripts/monium-cli.sh:*)
user-invocable: false
---
CLI: `monium-cli.sh <command> [args]`

Commands:
  search --service NAME --start "YYYY-MM-DD HH:MM:SS" [--end T] [--meta K=V] [--meta-type PATH] [--level LEVEL] [--filter TEXT] [--limit N] [--query LOGQL]

Auth: ~/.mcp_store/oauth_token or MONIUM_TOKEN
