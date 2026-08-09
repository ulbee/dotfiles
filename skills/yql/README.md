# yql

Выполнение YQL-запросов и получение результатов из YT/ClickHouse.

## CLI

`yql-cli.sh <command> [args]`

## Команды

| Команда | Описание |
|---------|----------|
| `run QUERY` | Синхронный запуск запроса |
| `submit QUERY` | Асинхронный запуск |
| `status OPERATION_ID` | Статус операции |
| `results OPERATION_ID` | Результаты операции |
| `get-query OPERATION_ID` | Текст запроса |
| `abort OPERATION_ID` | Отмена операции |

## Примеры

```bash
yql-cli.sh run "SELECT * FROM table LIMIT 10"
yql-cli.sh submit "SELECT count(*) FROM big_table"
yql-cli.sh results <operation_id>
```

## Авторизация

`~/.mcp_store/oauth_token` или `OAUTH_TOKEN`

Получить токен: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=60c90ec3a2b846bcbf525b0b46baac80
