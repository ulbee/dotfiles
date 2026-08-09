# intrasearch

Семантический поиск по wiki, документации, задачам Tracker, Stack Overflow и коду монорепо.

## CLI

`intrasearch-cli.sh <command> <query> [options]`

## Команды

| Команда | Описание |
|---------|----------|
| `search QUERY [--page-size N] [--product NAME]` | Wiki и документация |
| `stsearch QUERY` | Задачи Tracker |
| `sosearch QUERY` | Stack Overflow |
| `code-search QUERY [--page-size N]` | Код в монорепо |

## Операторы поиска

- `url:"<url>*"` — фильтр по URL
- `s_queue:"QUEUE"` — очередь (stsearch)
- `s_assignee:"login"` — исполнитель (stsearch)
- `s_language:"Go"` — язык (code-search)
- `s_project:"path"` — путь проекта (code-search)

## Авторизация

`~/.mcp_store/oauth_token` или `INTRASEARCH_TOKEN`

Получить токен: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=60c90ec3a2b846bcbf525b0b46baac80
