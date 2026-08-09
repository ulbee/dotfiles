---
name: experiments3
description: "Read and update experiments3 configs and experiments from tariff-editor API"
allowed-tools: Bash(skills/experiments3-cli.sh:*)
user-invocable: false
---
CLI: `experiments3-cli.sh <command> <args> [--tst]`

Commands:
  config NAME [--tst]                              Get config by name
  experiment NAME [--tst]                          Get experiment by name
  search-configs LIMIT OFFSET [--name=X] [--consumer=X] [--owner=X]  Search configs
  search-experiments LIMIT OFFSET [--name=X]       Search experiments
  draft-config NAME LAST_MODIFIED_AT 'JSON' [--tst]   Create config update draft
  draft-experiment NAME LAST_MODIFIED_AT 'JSON' [--tst] Create experiment update draft
  schema-draft-create TYPE NAME SCHEMA [SKIP_VALIDATE] [--default-value=JSON]
  schema-draft-get config_name=X | experiment_name=X | draft_id=X
  schema-draft-delete config_name=X | draft_id=X
  schema-publish DRAFT_ID [--namespace=X]          Publish schema draft

Options: --tst (testing env), --namespace=X (platform admin)
Auth: EXPERIMENTS3_TOKEN env var or ~/.mcp_store/oauth_token
Get token: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=60c90ec3a2b846bcbf525b0b46baac80
Run `help` for detailed usage and workflows.
