# DataLens Chart Creation Playbook

Этот reference закрывает write-path, которого не было в старой версии скилла.

## Что раньше делалось руками

Старый `yandex-datalens-analyst` умел только read-path:

- `getDashboard`
- `getWizardChart` / `getQLChart` / `getEditorChart`
- `/api/run`
- структурный разбор дашборда

Чтобы добавить новый чарт на дашборд, приходилось вручную:

1. взять `getQLChart` существующего чарта как шаблон;
2. заменить `data.queryValue`;
3. вызвать `createQLChart`;
4. проверить новый `chart_id` через `/api/run`;
5. взять `getDashboard`;
6. вручную собрать `widget` + `layout`;
7. вызвать `updateDashboard(mode=publish)`.

Теперь это завернуто в `scripts/chart_ops.py`.

## Новый CLI

### Проверить схему/колонку через dashsql

```bash
python3 scripts/chart_ops.py run-sql <CONNECTION_ID> \
  --sql "SELECT phone_pd_id FROM public.messages WHERE false"
```

Для тяжёлых таблиц это лучше, чем `SELECT * LIMIT 1`: PostgreSQL валидирует колонку, но не читает данные.

### Создать QL-чарт из существующего шаблона

```bash
python3 scripts/chart_ops.py clone-ql-chart <SOURCE_CHART_ID> \
  --chart-key "Users/aostrikov/swarm-generator-unique-users-by-day" \
  --sql "SELECT count(DISTINCT phone_pd_id) AS unique_users, date_trunc('day', created_at) AS day FROM public.messages WHERE phone_pd_id IS NOT NULL GROUP BY day ORDER BY day" \
  --description "Unique users per day based on distinct phone_pd_id" \
  --x-guid day --x-title day \
  --y-guid unique_users --y-title unique_users
```

### Добавить existing chart в dashboard

```bash
python3 scripts/chart_ops.py add-chart-to-dashboard <DASHBOARD_ID> <CHART_ID> \
  --widget-title "Unique Users per Day" \
  --tab-id 6E \
  --anchor-chart-id y0e8s618hb8wi \
  --position right
```

### Самый короткий путь: создать и сразу опубликовать

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

## Практические правила

- Для новой QL-метрики почти всегда клонируй существующий QL-чарт, а не собирай `visualization` с нуля.
- Если неясно, какая колонка соответствует пользователю/заказу/сегменту, сначала проверь схему через `run-sql`.
- Перед `publish` убедись, что `validation` вернул series/rows, а не пустой payload.
- Если виджет уже есть на табе, `add-chart-to-dashboard` вернёт `already_present` вместо дублирования.
- Если нужен безопасный прогон без записи, используй `--dry-run`.
