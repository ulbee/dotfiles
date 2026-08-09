---
name: tms
description: "Чтение тест-кейсов (ТК) из Yandex TMS — a.yandex-team.ru/tms. Парсит название, предусловия и шаги (Action → Expected result) по URL или id. Используй, когда нужно прочитать/пересказать тест-кейс или написать по нему автотест. Триггеры: ссылки вида a.yandex-team.ru/tms/projects/<p>/testcases/<id>, tms.yandex-team.ru, слова «тест-кейс», «ТК», «testcase», «TMS», номер кейса + проект."
allowed-tools: Bash(scripts/tms-cli.sh:*)
user-invocable: true
---

CLI: `scripts/tms-cli.sh <command> [args]`

Читает тест-кейсы Yandex TMS через REST API `https://api.tms.yandex-team.ru/v1`.

## Команды

```
get <url|id> [--project P] [--json]   Прочитать ТК: название, статус/приоритет,
                                       предусловия, шаги (Action → Expected).
search <term> [--project P] [--filter F] [--limit N] [--json]
                                       Поиск кейсов (по названию или TMS-фильтру).
project <id|url> [--json]              Метаданные проекта.
```

## Примеры

```bash
scripts/tms-cli.sh get https://a.yandex-team.ru/tms/projects/lm/testcases/876
scripts/tms-cli.sh get 876 --project lm
scripts/tms-cli.sh get 876 --project lm --json          # сырой JSON API
scripts/tms-cli.sh search 'Деактивация языка' --project lm
scripts/tms-cli.sh search x --project lm --filter 'tasks: "TMSLM-883"'
```

## Что возвращает `get` (читаемый вид)

- **Название** — `title` (+ `#id`).
- **Статус / Приоритет** — `status.key` / `priority.key`.
- **Предусловия** — нумерованный список из `preconditions[]`. Локальные (`type:"local"`)
  выводятся текстом; ссылочные (`type:"pointer"`) помечаются `[shared-условие #id]`.
- **Шаги** — из `steps[]`, для каждого: `Action` (`action`) и `Expected` (`expectation`).
  Ссылочные группы помечаются `[shared-группа шагов #id]`.
- **Связанные задачи** — `tasks[]` (ключи Трекера), если есть.

HTML-разметка в полях снимается; для точной структуры используй `--json`.

## Формат вывода пользователю (после `get`)

Пересказывай прочитанный кейс так (шаги — обязательно таблицей `# · Действие · Ожидание`,
жирным выделяй дословные строки UI: тексты нотификаций, тултипов, кнопок):

```markdown
## [МЯК][Лаба][Конструктор] Деактивация языка в НЕопубликованном курсе

**Статус:** actual · **Приоритет:** medium
[Открыть в TMS](https://a.yandex-team.ru/tms/projects/lm/testcases/887)

**Описание:** проверка деактивации языка в НЕопубликованном МЯ курсе.

### Предусловия
1. **НЕопубликованный** МЯ курс с языками `RU`, `EN`, где один пользователь начал проходить курс на `RU`
2. **НЕопубликованный** МЯ курс с языками `AB`, `DE` (ранее не публиковался)
3. Оба курса состоят из 1 модуля: Видео
4. Открыта страница курса из п.1, вкладка «Конструктор»

### Шаги

| # | Действие | Ожидание |
|---|----------|----------|
| 1 | Выбрать язык `RU` | Выбран `RU`; слева от тоггла «Отображать язык» появился значок предупреждения |
| 2 | Навести курсор на значок предупреждения | Тултип: **«Этот курс сейчас проходит 1 студент…»** |
| 3 | Кликнуть на тоггл «Отображать язык» | Нотификация **«Настройки языка изменены»**; тоггл → выкл; зачёркнутый глаз на табе |
```

После таблицы — короткий вывод «ключевого отличия»/сути кейса одной строкой, если он читается из шагов
(напр.: предупреждение о потере прогресса появляется только для языка, который кто-то проходит).

## Ключевые факты API (проверено по коду Arcadia)

- Endpoint: `GET /v1/projects/{PROJECT}/test-cases/{ID}` (путь `test-cases`, **не** `testcases`).
- Поле результата ожидания называется **`expectation`**, не `expected_result`.
- `PROJECT` — ключ из URL (`.../projects/lm/...` → `lm`), не числовой id.
- Prod ограничен 50 rps/IP (иначе `429`); для экспериментов есть preproduction
  (`TMS_API_BASE=https://api.tms-preproduction.yandex-team.ru/v1`).

## Авторизация

Нужен **TMS OAuth-токен** (client_id `a5337eb7fd4c4fa1ad85900a0487f0a3`).
Токен от arc/Arcanum к TMS API **не подходит**. Резолв (`scripts/token.sh`):
env `TMS_OAUTH_TOKEN`/`TMS_TOKEN`/`YA_TMS_TOKEN` → `TMS_TOKEN_CMD` → файлы
(`~/.arc/tms_token`, `~/.yandex/tms_token`, `~/.config/tms/token`) → macOS Keychain
(`tms-oauth-token`). При отсутствии токена CLI печатает инструкцию и ссылку на выдачу.
Токен никогда не логируется.
