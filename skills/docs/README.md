# docs

Чтение страниц docs.yandex-team.ru с OAuth авторизацией.

## CLI

`docs-cli.sh read <url-or-path>`

## Примеры

```bash
docs-cli.sh read arcanum/communication/public-api
docs-cli.sh read https://docs.yandex-team.ru/experiments3/quickstart
```

Если путь не начинается с `http`, автоматически подставляется `https://docs.yandex-team.ru/`.

## Авторизация

`~/.mcp_store/oauth_token` или `DOCS_TOKEN`

Получить токен: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=60c90ec3a2b846bcbf525b0b46baac80

## Ограничения

docs.yandex-team.ru — SPA, часть контента может быть загружена через JavaScript и не попасть в вывод.
