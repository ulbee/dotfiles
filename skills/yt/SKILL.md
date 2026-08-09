---
name: yt
description: >
  Выполняет операции через YT CLI (`yt`) для Cypress, file/table/dynamic table,
  map-reduce/vanilla, jobs, transactions, ACL, queue и query tracker.
  Использовать при запросах: "yt", "прочитай/запиши таблицу в yt",
  "запусти map-reduce", "mount-table", "insert-rows", "list-jobs",
  "queue consumer", "start-query", "покажи команды yt".
  Не использовать для Arcadia VCS (`arc`), Tracker API и Wiki API.
---

# YT CLI Skill

Скилл для безопасной и предсказуемой работы с `yt`.

## Когда использовать

- Чтение/запись таблиц в YT.
- Операции с dynamic tables, jobs, query tracker, ACL, queue.

## Когда не использовать

- Arcadia VCS (`arc`), Tracker API, Wiki API, DataLens.

## Порядок работы

1. Определить домен задачи: `cypress`, `table`, `dynamic table`, `operations`, `jobs`, `transactions`, `acl`, `queue`, `query tracker`.
2. Проверить окружение и CLI:
   - кластер по умолчанию `hahn`;
   - если `yt` не в `PATH`, использовать `~/yt-venv/bin/yt` (или `alias yt=~/yt-venv/bin/yt`);
   - если после fallback команда всё ещё недоступна, спросить пользователя, как подключить `yt`;
   - не искать бинарник по всему компьютеру.
3. Для нетривиальной команды открыть карту выбора:
   - [references/command-selection.md](references/command-selection.md)
4. Перед изменяющими действиями сделать безопасное чтение:
   - `yt exists <path>`
   - `yt get <path>` / `yt read <table> --format <fmt>` / `yt select-rows '<query> limit N' --format json`
5. Выполнить целевую команду с явным `--format`, где это важно.
6. Подтвердить результат отдельной проверкой (`yt get/read/select-rows/list-jobs/get-operation`).

## Особенности среды Codex

- YT-сетевые команды запускать сразу вне песочницы (`require_escalated`):
  `exists`, `get`, `list`, `read`, `select-rows`, `start-query`, операции.
- Не делать предварительные YT-запросы из sandbox.
- DNS-ошибки sandbox (`Could not resolve host`, `nodename nor servname provided`) не считать проблемой YT.

## Обязательные правила

- Использовать kebab-case для команд/флагов.
- Для входных/выходных таблиц использовать `--src` и `--dst`.
- Для составной сортировки/редьюса повторять флаг:
  - корректно: `--sort-by a --sort-by b`
  - некорректно: `--sort-by a,b`
- Не использовать deprecated алиасы dynamic-команд (`insert`, `delete`, `lookup`, `select`).
- Для `select-rows` всегда явно задавать `--format json`.
- Для sorted dynamic table не использовать row-index range в `read`; использовать `select-rows`.

## Обработка ошибок

1. `Authentication failed` / `Unauthorized`:
   - проверить `YT_TOKEN` и кластер (`YT_PROXY`/`--proxy`).
2. `no such path` / `resolve error`:
   - проверить путь через `yt exists <path>`.
3. Ошибки формата:
   - явно задать `--format`.
4. Ошибки операций:
   - `yt get-operation <op_id>`
   - `yt list-jobs --operation <op_id>`
   - `yt get-job-stderr <job_id> <op_id>`

## Что должно быть в ответе пользователю

- Какая команда выполнена.
- Какой объект прочитан/изменён.
- Результат валидации после выполнения.

## References

- Карта выбора команд: [references/command-selection.md](references/command-selection.md)
- Полные локальные документы CLI:
  - `../../../../yt/datahub-docs/ru/_includes/api/cli/cli.md`
  - `../../../../yt/datahub-docs/ru/_includes/api/cli/examples.md`
  - `../../../../yt/datahub-docs/ru/_includes/api/cli/commands.md`
