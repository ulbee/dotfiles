---
name: self-review
description: "Собрать фактический черновик self-review для разработчика в Яндексе: найти выполненные задачи в Tracker, связанные PR в Arcanum и сгруппировать достижения по целям за текущее полугодие."
allowed-tools: Bash(python3 scripts/self_review.py:*)
user-invocable: true
---

# Self Review

Собирай фактическую основу для self-review разработчика в Яндексе.

Навык должен:
- работать с текущим полугодием по умолчанию: `01.01-30.06` или `01.07-31.12`
- искать завершенные задачи в Tracker
- находить связанные PR в Arcanum
- группировать результат по достигнутым целям
- возвращать итоговый текст на русском языке
- не придумывать влияние, метрики или договоренности, которых нет в данных

Используй CLI:

```bash
python3 scripts/self_review.py draft
```

Если нужно уточнить период или область поиска, используй опции:

```bash
python3 scripts/self_review.py draft --year 2026 --half 1
python3 scripts/self_review.py draft --login my-login
python3 scripts/self_review.py draft --query 'assignee:my-login queue:MYTEAM'
python3 scripts/self_review.py collect --json
```

## Что делает CLI

- определяет отчетный период
- ищет задачи пользователя в Tracker по assignee
- оставляет только задачи, завершенные в отчетный период
- подтягивает связанные Arcanum PR из remote links тикетов
- строит группы достижений по родительским задачам, проектам или компонентам
- формирует готовый черновик self-review

## Правила использования

- Сначала запускай `draft`.
- Если данных мало или выборка слишком широкая, повтори с `--query`, `--login`, `--year` и `--half`.
- Если пользователь просит только сырые данные, используй `collect --json`.
- Итоговый ответ пользователю держи на русском.
- Если ты дописываешь текст поверх собранного черновика, явно опирайся только на найденные задачи, цели и PR.

## Команды

### `period`
Показать текущий или заданный период.

```bash
python3 scripts/self_review.py period
python3 scripts/self_review.py period --year 2026 --half 2
```

### `collect`
Собрать структурированные данные по задачам, PR и целям.

```bash
python3 scripts/self_review.py collect
python3 scripts/self_review.py collect --json --login my-login
```

### `draft`
Сгенерировать готовый черновик self-review на русском языке.

```bash
python3 scripts/self_review.py draft
python3 scripts/self_review.py draft --year 2026 --half 1 --query 'assignee:my-login queue:MYTEAM'
```

## Авторизация

- Tracker: `TRACKER_OAUTH_TOKEN` или `~/.tracker-token`
- Arcanum: `ARC_OAUTH_TOKEN`, `~/.arc/token` или `arc token show`

## Ограничения

- Группировка целей эвристическая: сначала родительская задача, затем проект, затем компоненты.
- Если тикеты были сняты с пользователя после завершения, стандартный поиск по `assignee` может их не найти. В таком случае сузь или расширь выборку через `--query`.
