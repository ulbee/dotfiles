---
name: wiki
allowed-tools: Bash(scripts/wiki-cli.sh:*)
description: Read wiki pages, get page trees, and page metadata from internal wiki
---
CLI: `wiki-cli.sh <command> <url-or-slug>`

Commands:
  read URL_OR_SLUG [--max-chars N]    Page content (use --max-chars 10000 for large pages)
  tree URL_OR_SLUG                    Subpage tree
  info URL_OR_SLUG                    Page metadata

Auth: ~/.mcp_store/oauth_token or WIKI_TOKEN
