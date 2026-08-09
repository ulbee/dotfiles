# YT CLI Command Selection

Использовать этот файл как карту выбора команды по задаче. Для полного списка опций смотреть `yt <command> --help` и `../../../../yt/datahub-docs/ru/_includes/api/cli/commands.md`.

## 1) Базовая диагностика окружения

```bash
yt --version
yt --help
yt <command> --help
```

Проверять перед выполнением:

- Кластер по умолчанию: `hahn`
- `YT_PROXY` или `--proxy <cluster>` (если не задано, использовать `hahn`)
- `YT_TOKEN` или `~/.yt/token`

## 2) Карта доменов

| Задача | Команды |
|---|---|
| Навигация и атрибуты Cypress | `exists`, `get`, `set`, `list`, `find`, `create`, `copy`, `move`, `remove` |
| Файлы в Cypress | `read-file`/`download`, `write-file`/`upload` |
| Таблицы (статические) | `read`, `write`, `alter-table`, `get-table-columnar-statistics` |
| Динамические таблицы | `mount-table`, `unmount-table`, `insert-rows`, `delete-rows`, `lookup-rows`, `select-rows`, `reshard-table` |
| Операции вычислений | `map`, `reduce`, `map-reduce`, `sort`, `merge`, `join-reduce`, `vanilla`, `erase` |
| Наблюдение за операциями и джобами | `track-op`, `get-operation`, `list-operations`, `list-jobs`, `get-job-stderr`, `get-job-spec` |
| Транзакции | `start-tx`, `ping-tx`, `commit-tx`, `abort-tx`, `lock`, `unlock` |
| Права доступа (ACL) | `check-permission`, `add-member`, `remove-member`, `issue-token`, `revoke-token` |
| Очереди | `register-queue-consumer`, `pull-queue`, `pull-consumer`, `advance-consumer`, `unregister-queue-consumer` |
| Query tracker | `start-query`, `get-query`, `read-query-result`, `get-query-result`, `abort-query`, `list-queries` |

## 3) Типовые безопасные последовательности

### Чтение таблицы

```bash
yt exists //path/to/table
yt read //path/to/table --format yson
```

### Запись таблицы

```bash
printf 'x=1\n' | yt write //path/to/table --format dsv
yt read //path/to/table --format dsv
```

### Запуск map-операции

```bash
yt map 'cat' \
  --src //path/in \
  --dst //path/out \
  --format yson
yt get //path/out/@row_count
```

### Работа с dynamic table

```bash
yt mount-table //path/dyn --sync
printf '{key=1;value="a";}\n' | yt insert-rows //path/dyn --format yson
printf '{key=1;}\n' | yt lookup-rows //path/dyn --format yson
```

### Отладка джобы

```bash
yt list-jobs --operation <operation_id>
yt get-job-stderr <job_id> <operation_id>
yt job-tool prepare-job-environment <operation_id> <job_id>
```

## 4) Критичные нюансы

- Для read/write и операций с табличным вводом-выводом задавать `--format` явно.
- Для составной сортировки повторять `--sort-by`/`--reduce-by` несколько раз.
- Команды `write-table` и `write-file` поддерживают транзакционную запись.
- Загруженные файлы не исполняемые по умолчанию; для запуска в джобе выставлять `--executable`.
- Для очередей и query tracker всегда указывать обязательные параметры (`partition-index`, `offset`, `engine`, `query_id` и т.д.).
