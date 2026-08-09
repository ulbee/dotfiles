# DataLens API and Analysis Playbook

Детальный справочник для сложных кейсов. Открывать только при необходимости.

## Архитектура

```text
Connection -> Dataset -> Chart (Wizard/QL/Editor) -> Dashboard
```

## API endpoints

### Public API (метаданные)

- Host: `https://api.datalens.yandex.net`
- Заголовки:
  - `Authorization: OAuth <token>`
  - `x-dl-api-version: 0`
  - `Content-Type: application/json`

Методы чтения:
- `getDashboard`
- `getWizardChart`
- `getQLChart`
- `getEditorChart`
- `getDataset`
- `getConnection`
- `getEntries`
- `getEntriesRelations`
- `listDirectory`

Стратегия определения типа чарта:
1. `getWizardChart`
2. `getQLChart`
3. `getEditorChart`

### Chart Data API (фактические данные)

- Endpoint: `POST https://charts.yandex-team.ru/api/run`
- Заголовки:
  - `Authorization: OAuth <token>`
  - `Content-Type: application/json; charset=utf-8`
- Body:

```json
{"id":"<chartId>","params":{}}
```

Ключевые поля ответа:
- `data.graphs[]`
- `data.graphs[].title`
- `data.graphs[].data[]`
- `data.head[]`
- `data.rows[]`
- `usedParams`
- `type`
- `config`

Важно:
- `x` в графиках обычно timestamp в миллисекундах UTC (`x / 1000`), но для QL-графиков ось X может быть индексной.

## Контекст селекторов

Перед расчетом фиксировать контекст:
- tab
- chart_id
- date_scale
- date_interval
- metric
- dimension
- продуктовые фильтры

Рекомендуемая команда:

```bash
python3 scripts/analyze.py --run-chart-with-tab-context <DASHBOARD_ID> <CHART_ID>
```

## Политика fallback

Если основной чарт не исполняется:
1. Повторить с tab context.
2. Использовать fallback-чарт.
3. В ответе указать `primary_chart_id`, `fallback_chart_id` и `confidence=low`.

## Confidence policy

- `high`: прямой чарт пользователя + корректный tab context.
- `medium`: прямой чарт без полного контекста.
- `low`: использован fallback-чарт.

## QL charts: что проверить отдельно

- `x` может быть не датой, а индексом категории.
- Реальные периоды могут лежать в `data.categories`.
- Формулу метрики проверять в конфиге QL-чарта (`queryValue`).

## Типичные вопросы и стратегия

### Сколько было X в периоде
1. `--list-charts`
2. выбрать релевантный чарт
3. `--run-chart-with-tab-context`
4. фильтр по периоду
5. sum/avg/last

### Тренд метрики
1. получить серию
2. сравнить последние периоды
3. описать динамику и абсолют/дельту

### Сравнение сервисов A/B
1. выбрать чарт со split по сервису
2. извлечь обе серии
3. сравнить значения и разницу

## Практические замечания

- Для массового обхода чартов делать последовательные запросы.
- 403 почти всегда означает отсутствие доступа токена к объекту.
- Источник истины — конкретный виджет пользователя; не переключаться молча на другой.
