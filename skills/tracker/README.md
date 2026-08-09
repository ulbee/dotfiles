# tracker

Управление задачами Yandex Tracker — просмотр, поиск, создание, обновление, комментирование и связывание задач.

## CLI

`scripts/tracker-cli.sh [--json] <command> [args]`

Глобальный флаг `--json` переключает вывод любой команды в машиночитаемый JSON.

## Команды

| Команда | Описание |
|---------|----------|
| `my-tasks` | Мои открытые задачи |
| `show TICKET` | Детали задачи |
| `search QUERY` | Поиск задач (Tracker Query Language) |
| `status TICKET STATUS` | Изменить статус |
| `create --queue Q --summary S [--description D] [--type T]` | Создать задачу |
| `update TICKET [--summary S] [--description D]` | Обновить задачу |
| `comment TICKET TEXT` | Добавить комментарий |
| `links TICKET` | Связи задачи |
| `link TICKET RELATED_TICKET [TYPE]` | Связать задачи |
| `changelog TICKET` | История изменений |
| `pr-id TICKET` | ID Arcanum PR по тикету |
| `projects` | Список проектов |

## Авторизация

Токен хранится в `~/.tracker-token` или переменной окружения `TRACKER_OAUTH_TOKEN`.

Получить токен: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=5f671d781aca402ab7460fde4050267b
