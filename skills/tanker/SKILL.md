---
name: tanker
description: "Manage Tanker translations: list projects/keysets/keys, get/create/update/delete keys, import/export"
allowed-tools: Bash(tanker-cli.sh:*)
user-invocable: false
---
CLI: `tanker-cli.sh <command> [args]`

Commands:
  projects                                          List all projects
  keysets PROJECT [BRANCH]                          List keysets
  keys PROJECT KEYSET [--search PAT] [--limit N] [--branch B]  List keys
  get-key PROJECT KEYSET KEY [--branch B]           Get key with translations
  update-key PROJECT KEYSET KEY LANG TEXT [--branch B]  Update translation
  delete-key PROJECT KEYSET KEY [--branch B]        Delete key
  import PROJECT KEYSET FILE [--mode MODE] [--branch B]  Bulk import from JSON
  export PROJECT KEYSET [--format FMT] [--languages L1,L2] [--branch B]  Export

Import modes: CREATE_MISSING_KEYS (default), CREATE_OR_UPDATE_KEYS, UPDATE_EXISTING_KEYS
Export formats: json (default), android, ios, xliff, po, csv
Translation statuses: APPROVED, TRANSLATED, REQUIRES_TRANSLATION

Auth: TANKER_API_TOKEN env var, ~/.tanker_token, or ~/.mcp_store/oauth_token
Get token: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=60c90ec3a2b846bcbf525b0b46baac80
