---
name: yql
description: "Execute YQL queries, check operation status, and retrieve results. Use when you need to run analytical queries on YT/ClickHouse data."
allowed-tools: Bash(scripts/yql-cli.sh:*)
user-invocable: false
---
CLI: `yql-cli.sh <command> [args]`

Commands:
  run "QUERY"                Synchronous execution
  submit "QUERY"             Async execution
  status OPERATION_ID        Check status
  results OPERATION_ID       Get results
  get-query OPERATION_ID     Get query text
  abort OPERATION_ID         Cancel operation

Auth: ~/.mcp_store/oauth_token or YQL_TOKEN
