# wiki

Чтение страниц wiki.yandex-team.ru, получение деревьев подстраниц и метаданных.

## CLI

`wiki-cli.sh <command> <url-or-slug>`

## Команды

| Команда | Описание |
|---------|----------|
| `read URL_OR_SLUG` | Содержимое wiki-страницы |
| `tree URL_OR_SLUG` | Дерево подстраниц |
| `info URL_OR_SLUG` | Метаданные страницы |

## Примеры

```bash
wiki-cli.sh read taxi/partnerproducts/pro/unit-tests
wiki-cli.sh tree taxi/partnerproducts/pro
```

## Авторизация

`~/.mcp_store/oauth_token` или `WIKI_TOKEN`

Получить токен: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=60c90ec3a2b846bcbf525b0b46baac80
