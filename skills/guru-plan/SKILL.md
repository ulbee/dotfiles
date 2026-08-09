---
name: guru-plan
description: Builds an autonomous execution plan for a Tracker issue by reading issue context, researching the codebase, and updating a structured plan comment.
---

Use this skill when the user wants a Tracker issue researched and planned with minimal back-and-forth.

Do planning only in this mode. Do not implement code unless the user explicitly switches to execution.

Hard rule: use Tracker and repo tools directly, and use `arc` instead of `git` for any VCS lookup.

All human-facing output for this skill must be in Russian: the plan comment, any follow-up Tracker comments, and the final response.

Execution rules:

1. Study the request and pick skills for implementation:
   - read the full user prompt and any runtime context before deep work; do not plan from a skimmed summary
   - from the available skills, choose which ones apply: some help during planning itself (research, domain conventions), others matter mainly when the user switches to execution
   - name chosen skills in the plan where it helps handoff: e.g. in intent bullets or under a relevant stage
2. Resolve issue context first:
   - extract the Tracker issue key or id from the prompt
   - call `tracker_get_issue`
   - call `tracker_get_issue_comments`
   - fetch links, changelog, or attachments only when they affect the plan
   - if the prompt or runtime context identifies the user who started the run, capture that as `starter_login`
   - do not infer `starter_login` from `arc user-info`
3. Work autonomously by default:
   - inspect the repo, nearby code, tests, configs, and docs before asking questions
   - treat human issue comments as fresh intent and stronger guidance than stale issue text
   - use subagents only when they reduce search time or improve analysis quality
   - ask the user only for real blockers, missing secrets, or product decisions that materially change the result
4. Reuse the issue plan comment instead of spamming new ones:
   - treat comments containing `<!-- auto-plan -->` or the heading `## Автономный план выполнения` as plan comments
   - if the issue already has a plan comment, update that comment with `tracker_edit_comment`
   - if several plan comments exist, update the newest one that still matches the current issue intent
   - if editing the existing plan comment is not possible, post a replacement comment that starts with `Заменяет план-комментарий <comment_id>`
5. Research before writing the plan:
   - identify the concrete user problem, expected behavior, likely entrypoints, neighboring tests, and rollout risks
   - prefer the smallest implementation shape that satisfies the issue
   - do not invent refactors, cleanup, or speculative follow-up work unless the issue requires them
6. Write the plan comment in markdown using this structure:

```md
<!-- auto-plan -->
## Автономный план выполнения

### Зафиксированное намерение
- ...

### Файлы, которые, вероятно, нужно изменить
- `path/to/file`: описание изменения человеческим языком

### Структуры данных и схемы
- ...

### Этапы выполнения
1. Название этапа
   - задача

### Критерии приемки
- ...

### Ключевые вопросы к пользователю
- ...
```

7. Section requirements:
   - `Зафиксированное намерение`: 2-5 bullets covering the problem, desired outcome, and non-goals
   - `Файлы, которые, вероятно, нужно изменить`: one bullet per file or code area with plain-English change intent
   - `Структуры данных и схемы`: name concrete types, payloads, config shapes, env vars, or write `Изменений схем не ожидается`
   - `Этапы выполнения`: group tasks by phase in implementation order
   - `Критерии приемки`: write testable bullets that execution can verify later
   - `Ключевые вопросы к пользователю`: only true blockers or product choices; if none, write `На этом этапе вопросов нет`
8. **Без плейсхолдеров** (иначе исполнителю или `guru-code` не за что зацепиться):
   - не оставляй TBD, «TODO позже», «добавить обработку ошибок / валидацию» без конкретики, шаги вида «аналогично этапу N» вместо повтора сути
   - если шаг предполагает команду или проверку — укажи что именно (какой тест, какой прогон, какой сценарий), в разумных пределах домена (не обязательно TDD на каждый тикет)
9. **Перед публикацией плана** — короткая самопроверка:
   - **покрытие тикета:** на каждое существенное требование из описания/комментариев есть этап или явный вывод «вне scope»
   - **скан на плохие шаблоны:** нет пунктов из п.8
   - **согласованность:** имена сущностей, путей и этапов не противоречат друг другу между секциями
10. When no plan comment exists yet:
   - post the plan with `tracker_add_comment`
   - if `starter_login` is known, summon that user with `summonees: [starter_login]`
   - if `starter_login` is unknown, post the plan without summon and mention that limitation in the final response
11. Final response must include:
   - the issue key
   - whether the plan comment was edited or created
   - the main implementation shape
   - the outstanding user questions, if any
