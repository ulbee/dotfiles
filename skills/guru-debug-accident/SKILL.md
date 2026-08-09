---
name: guru-debug-accident
description: Investigates dmp_suite task failures and incidents using Tracker MCP, DMP Admin MCP, Arc history, and Memory Bank. Use when debugging a failed task run, accident chain, root cause analysis, or incident report for a Yandex Tracker ticket.
---

# DMP: исследовать причину падения

## Когда применять

Скилл активируй для расследования падений ETL-тасков в `dmp_suite`: тикет в Трекере, инцидент в DMP Admin, поиск root cause, отчёт по шаблону.

## Источники в этом скилле

- **Полный сценарий** (все фазы Research / Analyze / Report, шаблон отчёта, шаги MCP): [command.md](command.md).

Подробные инструкции не дублируются здесь — следуй `command.md`.

## Обязательные действия агента

1. Выполни трёхфазный процесс из `command.md`: Research (включая изучение Memory Bank **до** глубокого разбора кода), Analyze, Report.
2. Пользуйся Tracker MCP и DMP Suite MCP для фактов; для кода и истории — `arc` (не `git`), как в `command.md`.
3. Веди JSON state в процессе расследования в соответствии с `command.md`.
4. Пользовательский текст — **на русском**.
