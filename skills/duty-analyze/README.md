# duty-analyze

Анализ дежурных тикетов — поиск логов пользователей через YQL, поиск appmetrica_device_id, инспекция событий мобильного приложения.

## CLI

`duty-analyze-cli.sh <command> [args]`

## Команды

| Команда | Описание |
|---------|----------|
| `get-device-id PHONE_OR_UID` | Найти appmetrica_device_id по телефону или uid |
| `get-mobile-logs DEVICE_ID [--days N]` | Получить логи мобильного приложения |
| `analyze-ticket TICKET` | Комбинированный анализ тикета |

## SQL-запросы

- `queries/get_device_id.sql` — поиск device_id
- `queries/get_mobile_logs.sql` — получение логов

## Авторизация

`~/.mcp_store/oauth_token` или `OAUTH_TOKEN` (для YQL)
