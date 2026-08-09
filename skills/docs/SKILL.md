---
name: docs
allowed-tools: Bash(scripts/docs-cli.sh:*)
description: Read docs.yandex-team.ru pages with OAuth authentication
---
CLI: `docs-cli.sh read <url-or-path>`

Commands:
  read URL_OR_PATH    Read a docs page (first 10000 chars)

URL auto-prepends https://docs.yandex-team.ru/ if not starting with http.
Auth: DOCS_TOKEN env var or ~/.mcp_store/oauth_token
Note: wiki.yandex-team.ru uses wiki-cli.sh, not this one.
