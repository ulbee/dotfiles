# monium

Поиск логов бэкенд-сервисов через Monium gRPC API.

## CLI

`monium-cli.sh <command> [args]`

## Команды

| Команда | Описание |
|---------|----------|
| `search --service NAME [--meta KEY=VALUE] [--level LEVEL] [--filter TEXT] [--limit N]` | Поиск логов |
| `services` | Список доступных gRPC-сервисов |

## Примеры

```bash
monium-cli.sh search --service my-service --meta order_id=abc123
monium-cli.sh search --service my-service --level ERROR --limit 50
```

## Авторизация

`~/.mcp_store/oauth_token` или `OAUTH_TOKEN`

Получить токен: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=60c90ec3a2b846bcbf525b0b46baac80
