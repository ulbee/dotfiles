---
name: yandex-datalens-analyst
description: >
  Анализ дашбордов Yandex DataLens и ответы на вопросы по данным.
  Используй этот скилл когда пользователь упоминает DataLens, дашборд, чарт, датасет,
  визуализацию, BI-аналитику в контексте Yandex. Скилл позволяет: получить структуру
  дашборда по ID, разобрать все чарты и селекторы, получить фактические данные из чартов,
  ответить на вопросы пользователя по данным дашборда, а также создать новый QL-чарт,
  проверить его и опубликовать виджет на дашборде.
  Триггерится на:
  "проанализируй дашборд", "что на этом дэше", "покажи данные из DataLens", "разбери чарт",
  "сколько было X в декабре", "какой тренд у метрики Y", "сделай новый чарт",
  "добавь чарт на деш", "создай график в datalens",
  ID дашборда вида abcdef12345, ссылки на datalens.yandex.cloud или datalens.yandex-team.ru,
  любые вопросы по метрикам и визуализациям в контексте DataLens.
---

# Yandex DataLens Analyst

Скилл для анализа и редактирования дашбордов DataLens через локальные скрипты:

- `scripts/analyze.py` for read-path: структура, чарты, селекторы, фактические данные.
- `scripts/chart_ops.py` for write-path: dashsql, createQLChart, add-chart-to-dashboard.

## Когда использовать

- Пользователь дал ID/URL дашборда и задаёт вопрос по метрикам.
- Нужно получить фактические значения из чартов, а не только метаданные.
- Нужно разобрать структуру дашборда (табы, чарты, селекторы, датасеты).
- Нужно создать новый QL-чарт по SQL.
- Нужно добавить existing chart в дашборд или опубликовать новый виджет.

## Когда не использовать

- Вопросы по YT/Tracker/Wiki/Arcadia.
- Запросы без контекста DataLens.

## Preconditions

```bash
export DATALENS_OAUTH_TOKEN="<oauth token>"
```

Если токен отсутствует, получить его можно по ссылке:
https://oauth.yandex-team.ru/authorize?response_type=token&client_id=09cea1cc285845b7b4dc3f409fcacad9

Поддерживается fallback:
- `--token-file <path>` для `scripts/analyze.py`, если переменная окружения не выставлена.
- `--token-file <path>` для `scripts/chart_ops.py`, если переменная окружения не выставлена.
- Token-файл может быть plain-text (один токен) или multi-token в формате `KEY="value"` — будет извлечён `DATALENS_OAUTH_TOKEN`.

Опционально:
```bash
export DATALENS_DASHSQL_HOST="https://back.datalens.yandex-team.ru"  # для dashsql, если отличается
```

## Базовый workflow (вопрос по данным)

### Короткий путь (предпочтительно, без ручных `jq`)

1. Извлечь `dashboard_id`.
2. Найти релевантный чарт по словам из вопроса:

```bash
python3 scripts/analyze.py <DASHBOARD_ID> --find-chart "country domain uniques" --find-limit 5
```

3. Посчитать top-N одной командой:

```bash
python3 scripts/analyze.py --run-topn <DASHBOARD_ID> <CHART_ID> \
  --period 2026-02 \
  --count-by uniques \
  --top-n 3
```

4. Вернуть пользователю `top`, `period_expr`, `used_params`, `chart_id`, `confidence`.

### Когда нужен ручной запуск чарта

```bash
python3 scripts/analyze.py --run-chart-with-tab-context <DASHBOARD_ID> <CHART_ID> \
  --params '{"eventdate_yshg":["__interval_2026-02-01T00:00:00.000Z_2026-02-28T23:59:59.999Z"]}'
```

### Когда непонятно значение селектора (например `count_by`)

```bash
python3 scripts/analyze.py --probe-selector-values <DASHBOARD_ID> <CHART_ID> count_by \
  --period 2026-02 \
  --probe-candidates '["hits","uniques","users"]'
```

## Базовый workflow (создание чарта на дашборде)

### Короткий путь: создать QL-чарт и сразу опубликовать виджет

```bash
python3 scripts/chart_ops.py clone-ql-to-dashboard <DASHBOARD_ID> <SOURCE_CHART_ID> \
  --chart-key "Users/aostrikov/swarm-generator-unique-users-by-day" \
  --sql "SELECT count(DISTINCT phone_pd_id) AS unique_users, date_trunc('day', created_at) AS day FROM public.messages WHERE phone_pd_id IS NOT NULL GROUP BY day ORDER BY day" \
  --widget-title "Unique Users per Day" \
  --anchor-chart-id y0e8s618hb8wi \
  --position right \
  --x-guid day --x-title day \
  --y-guid unique_users --y-title unique_users
```

### Создать stacked/grouped чарт с color dimension

```bash
python3 scripts/chart_ops.py clone-ql-chart <SOURCE_CHART_ID> \
  --chart-key "Users/aostrikov/messages-by-sender" \
  --sql "SELECT date_trunc('day', created_at) AS day, role AS sender, count(*) AS count FROM public.messages GROUP BY day, sender" \
  --x-guid day --x-title day \
  --y-guid count --y-title count \
  --color-guid sender --color-title sender
```

### Заменить чарт в существующем виджете дашборда

```bash
python3 scripts/chart_ops.py replace-chart-on-dashboard <DASHBOARD_ID> <OLD_CHART_ID> <NEW_CHART_ID> \
  --widget-title "Updated Chart Title"
```

### Если сначала нужно проверить схему/колонки

```bash
python3 scripts/chart_ops.py run-sql <CONNECTION_ID> \
  --sql "SELECT phone_pd_id FROM public.messages WHERE false"
```

### Если нужно только создать чарт, без публикации на dashboard

```bash
python3 scripts/chart_ops.py clone-ql-chart <SOURCE_CHART_ID> \
  --chart-key "Users/aostrikov/new-chart" \
  --sql "SELECT ..." \
  --description "..."
```

### Если нужно только прикрепить уже существующий chart_id

```bash
python3 scripts/chart_ops.py add-chart-to-dashboard <DASHBOARD_ID> <CHART_ID> \
  --widget-title "My Widget" \
  --tab-id 6E \
  --position right
```

## Универсальные паттерны ускорения

1. Всегда отделять "контекст вкладки" и "фактически применённые параметры":
- `tab_context.params` — дефолт вкладки;
- `used_params` — реальные параметры выполненного запроса.

2. Перед расчётами всегда проверять `used_params`:
- период;
- ключевые фильтры (сегмент, трек, профессия, страна, продукт и т.д.);
- уровень агрегации (`interval`, если задан).

3. Для периодов использовать `--period` и авто-нормализацию в `__interval_...`:
- `YYYY-MM` (например `2026-02`) автоматически конвертируется в полный месяц;
- при необходимости можно явно передать `--period-key`;
- в ответе всегда указывать `period_expr` из результата.

4. Термины пользователя могут быть двусмысленны (например, "секции", "скорость", "этап"):
- считать минимум 2 интерпретации, если это влияет на цифры (агрегированный этап и детализация по типам);
- явно подписывать, какую интерпретацию использовали для каждого числа.

5. Парсинг ответа всегда делать по типу полезной нагрузки:
- `metric_*` для индикаторов;
- `series[]` для графиков;
- `rows/columns` для таблиц.

6. При сравнении периодов показывать не только итог, но и сырой срез:
- помесячные точки/строки;
- агрегат (mean/sum/median);
- абсолютную и относительную разницу.

7. Для задач "топ стран/доменов/парков" по таблицам использовать `--run-topn` вместо ручного `jq`.
8. Для новых QL-метрик клонировать существующий QL-чарт, а не собирать `visualization` с нуля.
9. Для проверки колонок тяжёлых таблиц предпочитать `chart_ops.py run-sql` с `WHERE false`, а не `SELECT * LIMIT 1`.

## Fallback policy

Если основной чарт не исполняется (например, 403/427):
1. Повторить запуск с tab context, если запускали иначе.
2. Повторить запуск без tab context (`--run-chart`) с теми же params.
3. Если основной чарт всё ещё недоступен, использовать fallback-чарт:

```bash
python3 scripts/analyze.py --run-chart-with-tab-context <DASHBOARD_ID> <PRIMARY_CHART_ID> \
  --fallback-chart <FALLBACK_CHART_ID>
```

4. В ответе явно отметить выбранную стратегию и confidence:
- `high`: чарт выполнен с tab context;
- `medium`: чарт выполнен без tab context;
- `low`: использован fallback-chart.

## Частые режимы запуска

### Быстрый структурный анализ

```bash
python3 scripts/analyze.py <DASHBOARD_ID>
```

### Сохранить отчёт в файл

```bash
python3 scripts/analyze.py <DASHBOARD_ID> -o /tmp/report.json
```

### Инспекция чарта (SQL, connection, placeholders, colors)

```bash
python3 scripts/analyze.py --inspect-chart <CHART_ID>
```

### Найти чарт по смыслу вопроса

```bash
python3 scripts/analyze.py <DASHBOARD_ID> --find-chart "country domain uniques" --find-limit 5
```

### Top-N по таблице (без ручного jq)

```bash
python3 scripts/analyze.py --run-topn <DASHBOARD_ID> <CHART_ID> \
  --period 2026-02 \
  --count-by uniques \
  --top-n 3
```

### Подобрать валидные значения селектора

```bash
python3 scripts/analyze.py --probe-selector-values <DASHBOARD_ID> <CHART_ID> count_by \
  --period 2026-02 \
  --probe-candidates '["hits","uniques","users"]'
```

### Значение в периоде

```bash
python3 scripts/analyze.py --run-chart <CHART_ID> \
  --value-at-period 2026-01 --aggregate stack-sum
```

### Выполнить dashsql по connection

```bash
python3 scripts/chart_ops.py run-sql <CONNECTION_ID> \
  --sql "SELECT phone_pd_id FROM public.messages WHERE false"
```

### Создать QL-чарт из существующего шаблона

```bash
python3 scripts/chart_ops.py clone-ql-chart <SOURCE_CHART_ID> \
  --chart-key "Users/aostrikov/new-chart" \
  --sql "SELECT ..." \
  --x-guid day --x-title day \
  --y-guid metric --y-title metric
```

### Добавить existing chart в dashboard

```bash
python3 scripts/chart_ops.py add-chart-to-dashboard <DASHBOARD_ID> <CHART_ID> \
  --widget-title "My Widget" \
  --anchor-chart-id <ANCHOR_CHART_ID> \
  --position right
```

### Заменить чарт в существующем виджете

```bash
python3 scripts/chart_ops.py replace-chart-on-dashboard <DASHBOARD_ID> <OLD_CHART_ID> <NEW_CHART_ID> \
  --widget-title "New Title"
```

## Формат ответа пользователю (обязательный минимум)

Всегда указывать:
- итоговое значение и период;
- какой чарт использован (`chart_id` или `primary/fallback`);
- ключевые `params` селекторов;
- как считали (sum/avg/last/trend, aggregate mode);
- confidence: `high` / `medium` / `low`.

## Быстрые проверки

- Команда завершилась без ошибки.
- Данные действительно пришли из нужного чарта/таба.
- `used_params` соответствует нужному периоду и фильтрам.
- При fallback это явно отражено в тексте ответа.
- Для новых чартов `validation` вернул series/rows, а не пустой payload.
- Для publish-сценариев новый `chart_id` действительно появился в `--list-charts`.

## References

- Глубокий плейбук по API/типам чартов/нюансам: [references/api-and-analysis-playbook.md](references/api-and-analysis-playbook.md)
- Плейбук по созданию и публикации чартов: [references/chart-creation-playbook.md](references/chart-creation-playbook.md)
- Локальная справка CLI: `python3 scripts/analyze.py --help`
- Локальная справка write-path CLI: `python3 scripts/chart_ops.py --help`
