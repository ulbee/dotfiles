# ci-releases

Управление релизами Arcadia CI и пользовательскими сборками через gRPC API.

## CLI

`ci-releases-cli.sh <command> [args]`

## Команды

| Команда | Описание |
|---------|----------|
| `list DIR ACTION_ID [--limit N]` | Последние релизы |
| `changelog DIR ACTION_ID NUMBER` | Changelog релиза |
| `start DIR ACTION_ID [--branch BRANCH]` | Запустить релиз |
| `free-commits DIR ACTION_ID` | Незарелиженные коммиты |
| `run-custom DIR ACTION_ID [--branch BRANCH]` | Запустить custom action (deploy to testing) |

## Требования

- `pip3 install grpcio grpcio-tools`
- Сетевой доступ к `ci-public-api.yandex-team.ru:9091`

## Авторизация

`~/.ci/token` или `CI_OAUTH_TOKEN`
