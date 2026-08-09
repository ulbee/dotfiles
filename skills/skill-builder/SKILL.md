---
name: skill-builder
description: >
  Генератор скиллов для SkillStore: создание каркаса скилла с SKILL.md,
  CLI-скриптом и безопасной OAuth-авторизацией через Keychain.
  Включает полное руководство по авторизации, шаблоны и валидатор.
  Использует DeepAgent для поиска API-документации.
  Триггерится на: "создай скилл", "новый скилл", "skill builder", "скаффолд",
  "сгенерируй скилл", "шаблон скилла", "каркас скилла", "scaffold skill",
  "create skill", "build skill", "генератор скиллов".
---

# Skill Builder

Генератор скиллов для SkillStore. Создаёт готовую структуру с SKILL.md, CLI-скриптом
и (опционально) безопасной OAuth-авторизацией через системное хранилище.

## Installation

Этот скилл — директория с файлами SKILL.md + scripts/ + references/.
Для установки скопируй всю директорию в нужное место.

### Определи куда ставить

| Агент | Проверь существование | Куда ставить |
|-------|----------------------|-------------|
| **Claude Code** | `~/.claude/skills/` | `~/.claude/skills/skill-builder/` |
| **Cursor** | `~/.cursor/skills/` | `~/.cursor/skills/skill-builder/` |
| **Codex** | `~/.codex/` или `~/.agents/` | `~/.agents/skills/skill-builder/` |
| **Другой агент** | ничего из вышеперечисленного | `~/.ai-skills/skill-builder/` |

### Шаги установки

1. Определи агента (проверь какие директории из таблицы выше существуют)
2. Скопируй директорию `skill-builder/` (содержащую этот SKILL.md + scripts/ + references/) в путь из таблицы
3. Проверь: `python3 <путь_установки>/scripts/skill_builder.py ListTools`

### ВАЖНО: НЕ использовать

- `claude plugin install` — это другой механизм, скилл так НЕ ставится
- Не нужно создавать `plugin.json`, `package.json` или любые конфиг-файлы
- Установка = просто копирование директории в правильное место

## Preconditions

Скилл не требует токена. Работает автономно.

**Рекомендуется** установить из SkillStore:
- **DeepAgent** (`deepagent`) — для поиска документации по внутренним API Яндекса
- **SkillStore Tool** (`skillstore-tool`) — для загрузки готового скилла в каталог

## Запуск

```bash
python3 scripts/skill_builder.py <ToolName> --params '{"key":"value"}'
python3 scripts/skill_builder.py ListTools
```

## Инструменты

- `Scaffold` — создать каркас скилла без авторизации
- `ScaffoldWithAuth` — создать каркас скилла с OAuth через Keychain
- `RegenerateSkillMD` — перегенерировать SKILL.md из кода (секции Инструменты и Примеры)
- `Validate` — проверить скилл по чеклисту перед загрузкой в SkillStore
- `ListTemplates` — показать доступные шаблоны и рекомендованный workflow

## Workflow создания скилла

### Шаг 1: Исследование API (DeepAgent)

Если API — внутренний сервис Яндекса, используй скилл **DeepAgent** из SkillStore:

```bash
# Установи DeepAgent если ещё не установлен
python3 skillstore_tool.py DownloadSkill --params '{"slug":"deepagent","output_dir":"/tmp"}'

# Запроси документацию по API
python3 deepagent_tool.py Query --params '{"query":"Расскажи подробно про <название> API: базовый URL, авторизация, endpoints, формат запросов и ответов"}'
```

DeepAgent найдёт документацию по вики, трекеру и внутренним источникам и вернёт:
- Базовый URL и версию API
- Способ авторизации (OAuth client_id)
- Список endpoints с параметрами
- Формат ответов и примеры

### Шаг 2: Создание каркаса

```bash
# Без авторизации
python3 scripts/skill_builder.py Scaffold --params '{
  "skill_name": "my-service",
  "display_name": "My Service",
  "description": "Работа с My Service API",
  "base_url": "https://my-service.yandex-team.ru",
  "api_prefix": "/v1",
  "output_dir": "/tmp"
}'

# С OAuth-авторизацией (рекомендуется для внутренних API)
python3 scripts/skill_builder.py ScaffoldWithAuth --params '{
  "skill_name": "my-service",
  "display_name": "My Service",
  "description": "Работа с My Service API",
  "base_url": "https://my-service.yandex-team.ru",
  "api_prefix": "/v1",
  "oauth_client_id": "abc123def456",
  "output_dir": "/tmp"
}'
```

### Шаг 3: Реализация инструментов

Откройте сгенерированный `scripts/*_tool.py` и:

1. Добавьте функции инструментов в секцию `# Tools`
2. Зарегистрируйте их в словаре `TOOLS`

### Шаг 3.5: Обновление SKILL.md из кода

```bash
python3 scripts/skill_builder.py RegenerateSkillMD --params '{"skill_dir":"/tmp/my-service"}'
```

Автоматически обновит секции «Инструменты» и «Быстрые примеры» из TOOLS dict в коде.

### Шаг 4: Валидация

```bash
python3 scripts/skill_builder.py Validate --params '{"skill_dir":"/tmp/my-service"}'
```

### Шаг 5: Публикация в SkillStore

```bash
python3 skillstore_tool.py CreateSkill --params '{
  "path": "/tmp/my-service",
  "name": "My Service",
  "description": "Работа с My Service API",
  "author_name": "your-login",
  "tags": ["api", "service"]
}'
```

## Параметры Scaffold / ScaffoldWithAuth

| Параметр | Обязательный | Описание |
|----------|-------------|----------|
| `skill_name` | да | Имя скилла (латиница, дефисы: `my-service`) |
| `display_name` | да | Отображаемое название (`My Service`) |
| `description` | да | Описание скилла |
| `output_dir` | нет | Куда создать (по умолчанию `/tmp`) |
| `base_url` | нет | Базовый URL API |
| `api_prefix` | нет | Префикс API (`/v1`, `/v3`) |
| `oauth_client_id` | для auth | OAuth client_id (только ScaffoldWithAuth) |
| `service_name` | нет | Имя в Keychain (авто: `skill_store_<slug>`) |
| `token_env_var` | нет | Env-переменная (авто: `<SLUG>_TOKEN`) |
| `triggers` | нет | Триггер-фразы для description |
| `short_description` | нет | Краткое описание |

## Справочные материалы (references/)

В директории `references/` находятся полные руководства:

| Файл | Содержание |
|------|-----------|
| `SKILL_AUTHORING_GUIDE.md` | Полное руководство по созданию скиллов: структура, SKILL.md, чеклист, антипаттерны |
| `README_TOKEN_AUTH.md` | Шаблон безопасной авторизации: цепочка поиска токена, платформы, конвенции |
| `template_setup_token.py` | Шаблон скрипта интерактивной установки токена в Keychain |
| `template_token_auth.py` | Шаблон модуля авторизации (resolve_token, read_secret, check_html_auth_error) |

При создании скилла **прочитай** эти файлы для полного понимания паттернов.

## Конвенция именования (OAuth)

| Скилл | SERVICE_NAME | OAuth client_id |
|-------|-------------|-----------------|
| femida | `skill_store_femida` | `a09655c02a3143adb991b8debbd5fdee` |
| tracker | `skill_store_tracker` | `5f671d781aca402ab7460fde4050267b` |
| wiki | `skill_store_wiki` | `fd86e23a4d1347c1a65112f404210d46` |
| datalens | `skill_store_datalens` | `09cea1cc285845b7b4dc3f409fcacad9` |
| deepagent | `skill_store_deepagent` | `63fa6b57898e4b74a1a820c54cf144b8` |
| staff | `skill_store_staff` | `a09655c02a3143adb991b8debbd5fdee` |

**Правило:** `SERVICE_NAME` всегда с префиксом `skill_store_` для изоляции от системных ключей.

## Важно

- **Скрипты stdlib-only** — без внешних зависимостей (requests, httpx и т.д.)
- **Используй `urllib.request`** из стандартной библиотеки
- **Никогда не хардкодь пути** — используй `scripts/tool.py`, агент сам разрешит путь
- **Всегда добавляй секцию Installation** — без неё скилл не установится
- **DeepAgent** — главный инструмент для исследования внутренних API перед созданием скилла
