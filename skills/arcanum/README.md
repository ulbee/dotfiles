# arcanum

Просмотр метаданных PR, диффов, измененных файлов, отправка комментариев к ревью и управление worktree.

## CLI

`arcanum-cli.sh <command> [args]`

## Команды

| Команда | Описание |
|---------|----------|
| `pr-status PR_ID` | Статус PR |
| `pr-data PR_ID` | Метаданные + комментарии |
| `changed-files PR_ID` | Список измененных файлов |
| `file-diff PR_ID PATH` | Дифф файла |
| `file-content PR_ID PATH` | Содержимое файла на HEAD PR |
| `checks PR_ID [--failed\|--required\|--pending\|--active] [--json]` | CI/merge checks |
| `check-log PR_ID CHECK_TYPE` | Детали конкретной проверки |
| `ci-jobs PR_ID [CHECK_TYPE]` | Sandbox-задачи CI |
| `ci-log TASK_ID [LOG_FILE]` | Логи Sandbox-задачи |
| `ci-errors TASK_ID` | Анализ ошибок (формат, тесты, сборка) |
| `ci-failed PR_ID` | Все упавшие задачи с анализом |
| `open-issues PR_ID` | Открытые замечания ревью |
| `post-comment PR_ID --content TEXT [--file PATH] [--line N]` | Отправить комментарий |
| `reply COMMENT_ID --content TEXT` | Ответить на комментарий |
| `close-issue COMMENT_ID` | Закрыть замечание |
| `publish-drafts PR_ID` | Опубликовать черновики |
| `labels PR_ID [--add\|--remove\|--set LABEL]` | Управление лейблами |
| `run-action PR_ID CHECK_TYPE` | Запустить CI action |
| `deploy-testing PR_ID SERVICE` | Деплой в тестинг |
| `worktree-create NAME\|PR_ID [PATH]` | Создать worktree |
| `worktree-remove PATH` | Удалить worktree |
| `worktree-list [--status]` | Список worktree |

## Авторизация

`~/.arc/token` или `ARC_OAUTH_TOKEN`

## API

- V1: `arcanum.yandex.net/api/v1/...` (checks, comments, labels, active-diff)
- V2: `arcanum.yandex.net/api/v2/public/...` (comments CRUD, changelist, draft publish)
