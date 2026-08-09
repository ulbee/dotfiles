---
name: skillstore
description: >
  Управление каталогом скиллов SkillStore: загрузка, поиск, версионирование,
  перемещение, удаление скиллов, CRUD категорий, AI-подсказки разделов,
  скачивание, комментарии с рейтингом, анализ безопасности, статистика. Работает через stdlib-only Python CLI.
  Триггерится на: "skillstore", "скиллстор", "каталог скиллов", "загрузи скилл",
  "найди скилл", "поиск скиллов", "список скиллов", "категории скиллов",
  "удали скилл", "переместить скилл", "новая версия скилла", "скачай скилл",
  "безопасность скилла", "проверить безопасность".
---

# SkillStore Skill

Скилл для работы с каталогом SkillStore через `scripts/skillstore_tool.py`.

## Когда использовать

- Загрузка новых скиллов (файл или директория — автоупаковка в zip).
- Поиск скиллов по тексту, regex, тегу, категории.
- Просмотр списка скиллов и подробной информации.
- Создание новых версий скилла (с файлом или только метаданные: описание, теги).
- Перемещение скиллов между категориями (одиночное и массовое).
- Удаление скиллов.
- Управление категориями: создание, редактирование, удаление.
- AI-подсказка категории для нового скилла.
- Скачивание файла скилла (последняя или конкретная версия).
- Комментарии к скиллам: просмотр, создание (с оценкой 1-5 звёзд), удаление.
- Проверка безопасности скилла: запуск LLM-анализа, просмотр вердиктов.
- Статистика каталога.

## Когда не использовать

- Работа с Arcadia VCS — используй скилл `arcadia`.
- Работа с Tracker/Wiki/Femida — используй соответствующие скиллы.

## Preconditions

```bash
# Опционально — переопределить базовый URL (по умолчанию https://dab512.aimarvel.yandex.net)
export SKILLSTORE_BASE_URL="https://dab512.aimarvel.yandex.net"
```

Скилл не требует токена — SkillStore работает без аутентификации.

## Installation

Этот скилл — директория с SKILL.md + scripts/skillstore_tool.py.

### Определи куда ставить

| Агент | Проверь существование | Куда ставить |
|-------|----------------------|-------------|
| **Claude Code** | `~/.claude/skills/` | `~/.claude/skills/skillstore/` |
| **Cursor** | `~/.cursor/skills/` | `~/.cursor/skills/skillstore/` |
| **Codex** | `~/.codex/` или `~/.agents/` | `~/.agents/skills/skillstore/` |
| **Другой агент** | ничего из вышеперечисленного | `~/.ai-skills/skillstore/` |

### ВАЖНО: правила установки скиллов

1. **НИКОГДА не устанавливай скиллы в /tmp, временные или рабочие директории** — скиллы в temp удалятся при перезагрузке и не будут доступны агенту при старте.
2. **Устанавливай ТОЛЬКО в папку скиллов агента** — это директория, которая автоматически загружается при старте агента (см. таблицу выше).
3. **Структура**: `{skills_dir}/{skill_name}/SKILL.md` + `{skills_dir}/{skill_name}/scripts/*.py`
4. **При DownloadSkill**: всегда используй `output_dir` = папка скиллов агента, НЕ `/tmp`.

### Шаги установки

1. Определи агента (проверь какие директории из таблицы выше существуют)
2. Скачай скилл: `DownloadSkill --params '{"slug":"...","output_dir":"~/.claude/skills/"}'`
3. Распакуй в папку скиллов (если архив)
4. Проверь: `python3 ~/.claude/skills/skillstore/scripts/skillstore_tool.py ListTools`

## Запуск

```bash
python3 scripts/skillstore_tool.py <ToolName> --params '{"key":"value"}'
python3 scripts/skillstore_tool.py <ToolName> --params-file /tmp/params.json
python3 scripts/skillstore_tool.py ListTools
```

## Инструменты

### Скиллы

- `ListSkills` — список скиллов с фильтрацией и пагинацией
- `SearchSkills` — поиск скиллов (текст или regex)
- `GetSkill` — подробная информация о скилле по slug
- `CreateSkill` — создать новый скилл (файл/директория → zip → upload)
- `DeleteSkill` — удалить скилл
- `MoveSkills` — переместить скиллы в другую категорию
- `DownloadSkill` — скачать файл скилла (опционально конкретную версию)
- `SuggestCategory` — AI-подсказка категории

### Категории

- `ListCategories` — дерево категорий
- `CreateCategory` — создать категорию
- `UpdateCategory` — обновить категорию
- `DeleteCategory` — удалить категорию (с миграцией скиллов)

### Версии

- `ListVersions` — список всех версий скилла
- `CreateVersion` — создать новую версию (файл опционален; можно обновить только описание/теги)
- `DownloadVersion` — скачать конкретную версию скилла

### Комментарии

- `ListComments` — комментарии к скиллу (опционально по версии)
- `CreateComment` — создать комментарий с оценкой 1-5 звёзд
- `DeleteComment` — удалить комментарий по ID

### Безопасность

- `AnalyzeSecurity` — запустить LLM-анализ безопасности версии скилла

### AI

- `AiSearchSkills` — AI-поиск скиллов по описанию задачи/процесса/бизнес-кейса

### Прочее

- `GetStats` — статистика каталога
- `ListTools` — список всех инструментов

## Быстрые примеры

```bash
# Список скиллов
python3 scripts/skillstore_tool.py ListSkills --params '{}'

# Поиск по тексту
python3 scripts/skillstore_tool.py SearchSkills --params '{"query":"femida"}'

# Regex-поиск
python3 scripts/skillstore_tool.py SearchSkills --params '{"query":"agent|bot","regex":true}'

# Поиск по тегу
python3 scripts/skillstore_tool.py SearchSkills --params '{"tag":"cli"}'

# Подробности скилла
python3 scripts/skillstore_tool.py GetSkill --params '{"slug":"femida-hr"}'

# Загрузка скилла (директория → zip → upload)
python3 scripts/skillstore_tool.py CreateSkill --params '{"path":"/path/to/skill_dir","name":"My Skill","description":"Описание","author_name":"login"}'

# Переместить скиллы
python3 scripts/skillstore_tool.py MoveSkills --params '{"slugs":["skill-1","skill-2"],"category_path":"devtools/cli"}'

# Удалить скилл
python3 scripts/skillstore_tool.py DeleteSkill --params '{"slug":"my-skill"}'

# Категории
python3 scripts/skillstore_tool.py ListCategories --params '{}'
python3 scripts/skillstore_tool.py CreateCategory --params '{"path":"ai/agents/rag","display_name":"RAG-агенты","description":"Скиллы для RAG"}'
python3 scripts/skillstore_tool.py DeleteCategory --params '{"path":"ai/agents/rag","move_skills_to":"ai/agents"}'

# AI-подсказка категории
python3 scripts/skillstore_tool.py SuggestCategory --params '{"name":"My Skill","description":"Описание скилла"}'

# Статистика
python3 scripts/skillstore_tool.py GetStats --params '{}'

# Скачать и установить скилл (в папку скиллов агента, НЕ в /tmp!)
python3 scripts/skillstore_tool.py DownloadSkill --params '{"slug":"femida-hr","output_dir":"~/.claude/skills/"}'

# Скачать конкретную версию скилла
python3 scripts/skillstore_tool.py DownloadSkill --params '{"slug":"femida-hr","version":1,"output_dir":"~/.claude/skills/"}'

# Версии
python3 scripts/skillstore_tool.py ListVersions --params '{"slug":"my-skill"}'

# Новая версия с файлом
python3 scripts/skillstore_tool.py CreateVersion --params '{"slug":"my-skill","path":"/path/to/new/version","uploaded_by":"login","changelog":"Исправлены баги"}'

# Новая версия — только обновить описание и теги (без файла)
python3 scripts/skillstore_tool.py CreateVersion --params '{"slug":"my-skill","uploaded_by":"login","description":"Новое описание","tags":["cli","tool"],"changelog":"Обновлено описание"}'

python3 scripts/skillstore_tool.py DownloadVersion --params '{"slug":"my-skill","version":1,"output_dir":"/tmp"}'

# AI-поиск по задаче
python3 scripts/skillstore_tool.py AiSearchSkills --params '{"query":"Нужно автоматизировать процесс найма — поиск кандидатов и скрининг резюме"}'

# Комментарии
python3 scripts/skillstore_tool.py ListComments --params '{"slug":"my-skill"}'
python3 scripts/skillstore_tool.py ListComments --params '{"slug":"my-skill","version":2}'
python3 scripts/skillstore_tool.py CreateComment --params '{"slug":"my-skill","version_number":1,"author_login":"login","text":"Отличный скилл!","rating":5}'
python3 scripts/skillstore_tool.py DeleteComment --params '{"comment_id":42}'

# Анализ безопасности
python3 scripts/skillstore_tool.py AnalyzeSecurity --params '{"slug":"my-skill","version":1}'
```

## Безопасность скиллов (ОБЯЗАТЕЛЬНО)

### Поле `security_verdict` в списке скиллов

`ListSkills` и `SearchSkills` возвращают для каждого скилла поле `security_verdict`:

| Значение | Значение | Что делать |
|----------|----------|------------|
| `"safe"` | Все файлы безопасны | Можно устанавливать без предупреждений |
| `"data"` | Скилл обоснованно использует данные (API, сеть, файлы) | Можно устанавливать, упомянуть что скилл использует внешние данные |
| `"dangerous"` | Обнаружены угрозы безопасности | **⚠️ ОБЯЗАТЕЛЬНО предупредить пользователя!** Не устанавливать без явного подтверждения |
| `null` | Безопасность не проверена | Рекомендовать запустить проверку через `AnalyzeSecurity` |

### Правила для агента

1. **При поиске/списке скиллов**: всегда обращай внимание на `security_verdict`. Если вердикт `"dangerous"` — **обязательно предупреди пользователя** перед любыми действиями со скиллом.

2. **При установке скилла**: если `security_verdict` равен `"dangerous"` — **остановись и предупреди**:
   > ⚠️ Скилл «{name}» отмечен как **небезопасный**. Обнаружены потенциальные угрозы. Устанавливать только после явного подтверждения.

3. **Если `security_verdict` = `null`**: предложи запустить проверку:
   ```bash
   python3 scripts/skillstore_tool.py AnalyzeSecurity --params '{"slug":"...","version":...}'
   ```

4. **Результат `AnalyzeSecurity`**: возвращает `overall_score` (0-100) и `files` с вердиктами по каждому файлу. Покажи пользователю файлы с вердиктом `"dangerous"` и их `reason`.

5. **При рекомендациях скиллов**: сортируй безопасные выше небезопасных. Если все найденные скиллы `"dangerous"` — явно предупреди.

### Пример работы

```bash
# 1. Поиск скиллов — обрати внимание на security_verdict в ответе
python3 scripts/skillstore_tool.py SearchSkills --params '{"query":"rag"}'
# → skills[].security_verdict: "safe" | "data" | "dangerous" | null

# 2. Если null — запусти анализ
python3 scripts/skillstore_tool.py AnalyzeSecurity --params '{"slug":"rag-tool","version":1}'
# → {status: "completed", overall_score: 95, files: {...}}
```

## Типичные сценарии

### Найти slug скилла по имени

Большинство команд требуют `slug`, а не имя. Если знаешь только имя — сначала найди slug через `SearchSkills`:

```bash
# Найти slug по имени
python3 scripts/skillstore_tool.py SearchSkills --params '{"query":"Пакетное выполнение"}'
# → в ответе skills[].slug — это нужный slug
```

### Удалить скилл, зная только имя

```bash
# 1. Найти slug
python3 scripts/skillstore_tool.py SearchSkills --params '{"query":"Мой скилл"}'
# 2. Удалить по slug из ответа
python3 scripts/skillstore_tool.py DeleteSkill --params '{"slug":"skill-e47ec601"}'
```

### Обновить описание скилла, зная только имя

```bash
# 1. Найти slug
python3 scripts/skillstore_tool.py SearchSkills --params '{"query":"Мой скилл"}'
# 2. Обновить метаданные
python3 scripts/skillstore_tool.py CreateVersion --params '{"slug":"my-skill","uploaded_by":"login","description":"Новое описание","changelog":"Обновил описание"}'
```

### Оставить баг-репорт на скилл

```bash
# 1. Найти slug и текущую версию
python3 scripts/skillstore_tool.py SearchSkills --params '{"query":"Проблемный скилл"}'
python3 scripts/skillstore_tool.py ListVersions --params '{"slug":"found-slug"}'
# 2. Оставить комментарий
python3 scripts/skillstore_tool.py CreateComment --params '{"slug":"found-slug","version_number":1,"author_login":"login","text":"🐛 Баг: ...","rating":2}'
```

> **Правило**: всегда начинай с `SearchSkills`, если не знаешь slug. Не пытайся угадать slug или обращаться к API напрямую.

## Порядок работы при загрузке

1. Указать `path` — файл или директория.
2. Если директория — автоматически упаковывается в zip.
3. Если файл не .zip — упаковывается в zip.
4. Если .zip — загружается как есть.
5. Указать `name`, `description`, `author_name`.
6. Опционально: `category_path`, `tags`, `short_description`.
7. Если `category_path` не указан — можно вызвать `SuggestCategory` для AI-подсказки.

## Обновление скилла

Для обновления описания, тегов или файла скилла — используй `CreateVersion`:
- С файлом: указать `path`, `uploaded_by`, опционально `description`, `tags`, `changelog`
- Без файла: указать только `uploaded_by` + нужные метаданные (`description`, `tags`, `changelog`)
- Если description/tags не указаны — наследуются от предыдущей версии

## Обратная связь при ошибках (ОБЯЗАТЕЛЬНО)

При работе с ЛЮБЫМ скиллом из каталога — если возникла ошибка, баг или неожиданное поведение:

1. **Оставь комментарий** в SkillStore с баг-репортом:
```bash
python3 scripts/skillstore_tool.py CreateComment --params '{
  "slug": "<slug-скилла-с-ошибкой>",
  "version_number": <номер-версии>,
  "author_login": "<твой-логин>",
  "text": "🐛 Баг-репорт\n\nОшибка: <описание ошибки>\nОжидалось: <ожидаемое поведение>\nПолучено: <фактическое поведение>\n\nШаги воспроизведения:\n1. ...\n2. ...\n\n💡 Предложение: <как исправить, если есть идеи>",
  "rating": 2
}'
```

2. **Формат баг-репорта** (шаблон):
   - `🐛 Баг-репорт` — заголовок
   - `Ошибка:` — краткое описание проблемы
   - `Ожидалось:` — что должно было произойти
   - `Получено:` — что произошло на самом деле (включая текст ошибки)
   - `Шаги воспроизведения:` — как повторить
   - `💡 Предложение:` — идеи по исправлению (если есть)

3. **Рейтинг при ошибках**:
   - `1` — скилл не работает совсем
   - `2` — скилл работает частично, есть критичные баги
   - `3` — скилл работает, но есть заметные проблемы

4. **Когда оставлять**: при ЛЮБОЙ ошибке — HTTP-ошибки, невалидный вывод, неожиданное поведение, устаревшая документация, неработающие примеры.

> Это помогает авторам быстро находить и исправлять проблемы. Не молчи — репорти!
