---
name: datacatalog
description: >
  Поиск и изучение данных в DataCatalog (data.yandex-team.ru).
  Используй когда нужно: найти таблицу по названию или пути, получить схему таблицы
  (список колонок с типами и описаниями), прочитать описание датасета, узнать какие
  колонки реально используются, найти из каких таблиц строится датасет (родительские
  источники) или какие таблицы строятся из него (дочерние).
  Триггерится на:
  упоминание "DataCatalog", "data catalog", "data.yandex-team.ru",
  запросы вида "найди таблицу", "схема таблицы", "что в таблице", "колонки таблицы",
  "data_entity_id", "откуда данные в ...", "что строится из ...",
  пути YT вида //home/..., //statbox/..., //logs/... (когда нужна схема или описание),
  вопросы о структуре датасета, его источниках и потребителях.
allowed-tools: Bash(scripts/datacatalog-cli.sh:*)
---

# DataCatalog Skill

Скилл для работы с [DataCatalog](https://data.yandex-team.ru) — каталогом данных Яндекса.
Использует `scripts/datacatalog-cli.py` через обёртку `scripts/datacatalog-cli.sh`.

## Команды

### `search <query>` — Поиск датасетов

```bash
scripts/datacatalog-cli.sh search "grut_enriched/assets"
scripts/datacatalog-cli.sh search "//logs/bs-action-checked-log/1d"
scripts/datacatalog-cli.sh search "product_money"
```

Возвращает таблицу `data_entity_id|slug|logtype`. Из результатов выбери строку, чей
slug наиболее точно соответствует запросу.

### `search-in-cluster <query> <cluster>` — Поиск с фильтром по кластеру

```bash
scripts/datacatalog-cli.sh search-in-cluster "client_revenue" hahn
scripts/datacatalog-cli.sh search-in-cluster "comdep/campaigns" arnold
```

Кластеры: `hahn`, `arnold`, `kolmogorov`.

### `schema-by-path <//yt/path>` — Схема таблицы по YT-пути

```bash
scripts/datacatalog-cli.sh schema-by-path //statbox/cube/daily/grut_enriched/assets/2025-02-11
scripts/datacatalog-cli.sh schema-by-path //home/bs/logs/AdsCaesarOrdersFullDump/latest
```

Путь **обязан** начинаться с `//`. Возвращает таблицу `name|type|description` и `data_entity_id`.

### `schema-by-id <data_entity_id>` — Схема по ID датасета

```bash
scripts/datacatalog-cli.sh schema-by-id 2045844082
```

Возвращает `name|type|description`, `table_path`, опционально `Logtype`.

### `description <data_entity_id>` — Описание датасета

```bash
scripts/datacatalog-cli.sh description 2045844082
```

Возвращает текстовое описание: что содержит таблица, как собираются данные,
ссылки на wiki, дашборды, YQL-примеры.

### `usage-columns <data_entity_id>` — Используемые колонки

```bash
scripts/datacatalog-cli.sh usage-columns 2045844082
```

Список колонок, которые реально использовались в запросах за последние 2 дня.

### `usage-parents <data_entity_id>` — Родительские источники

```bash
scripts/datacatalog-cli.sh usage-parents 2045844082
```

Таблицы, из которых строится данный датасет (входные источники).
Формат: `data_entity_id|slug|owners`.

### `usage-children <data_entity_id>` — Дочерние датасеты

```bash
scripts/datacatalog-cli.sh usage-children 2045844082
```

Таблицы, которые строятся на основе данного датасета (выходные потребители).
Формат: `data_entity_id|slug|owners`.

## Типичный workflow

**Пользователь спрашивает про таблицу `//home/project/my_table`:**

1. `scripts/datacatalog-cli.sh schema-by-path //home/project/my_table` — получить схему
2. Если нужно описание: взять `data_entity_id` из шага 1, затем `description <id>`
3. Если нужны источники: `usage-parents <id>`

**Пользователь знает только название, не знает путь:**

1. `scripts/datacatalog-cli.sh search "my_table_name"` — найти data_entity_id
2. `scripts/datacatalog-cli.sh schema-by-id <id>` — получить схему

## Auth

Токен берётся (в порядке приоритета):
1. `DATACATALOG_TOKEN` env var
2. `DC_TOKEN` env var
3. `~/.datacatalog_token` (файл с OAuth-токеном)

OAuth-токен можно получить по инструкции: https://docs.yandex-team.ru/datacatalog/api/intro

## Интерпретация результатов поиска

Поле `slug` имеет формат `yt://cluster?path=//...`. Если в пути встречается `*`,
на его месте должна стоять дата. Поле `logtype` — имя таблицы в Logos (используется
для получения информации о timedelta и формате дат).
