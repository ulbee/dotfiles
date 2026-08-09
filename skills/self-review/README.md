# self-review

Навык для подготовки фактического черновика self-review разработчика в Яндексе.

Он собирает:
- завершенные за полугодие задачи из Tracker
- связанные PR из Arcanum
- группы достижений по целям

## CLI

`python3 scripts/self_review.py <command> [args]`

## Команды

| Команда | Описание |
|---------|----------|
| `period` | Показать текущий или заданный отчетный период |
| `collect` | Собрать структурированные данные по задачам, PR и целям |
| `draft` | Сгенерировать черновик self-review на русском |

## Примеры

```bash
python3 scripts/self_review.py draft
python3 scripts/self_review.py draft --year 2026 --half 1
python3 scripts/self_review.py draft --login my-login
python3 scripts/self_review.py draft --query 'assignee:my-login queue:MYTEAM'
python3 scripts/self_review.py collect --json
```

## Авторизация

- Tracker: `~/.tracker-token` или `TRACKER_OAUTH_TOKEN`
- Arcanum: `~/.arc/token`, `ARC_OAUTH_TOKEN` или `arc token show`

## Как определяется период

- `half=1`: с января по июнь
- `half=2`: с июля по декабрь

По умолчанию используется текущее полугодие.
