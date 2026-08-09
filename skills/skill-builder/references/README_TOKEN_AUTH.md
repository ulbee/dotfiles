# Шаблон безопасной авторизации для скиллов

Кроссплатформенная авторизация через системное хранилище секретов.
Агент **никогда не видит** значение токена.

## Быстрый старт

### 1. Скопируйте шаблоны в свой скилл

```
your-skill/
  scripts/
    setup_token.py      ← копия template_setup_token.py
    your_tool.py         ← основной инструмент
```

### 2. Замените константы

**ВАЖНО:** Имя сервиса в Keychain всегда с префиксом `skill_store_` для изоляции от системных ключей.

В `setup_token.py`:
```python
SERVICE_NAME = "skill_store_tracker"   # ← всегда с префиксом!
SERVICE_DISPLAY = "Tracker"
OAUTH_URL = "https://oauth.yandex-team.ru/authorize?..."
```

В `your_tool.py` (скопируйте функции из `template_token_auth.py`):
```python
SERVICE_NAME = "skill_store_tracker"   # ← тот же ключ что в setup_token.py
TOKEN_ENV_VAR = "TRACKER_TOKEN"
TOKEN_FILE_ENV_VAR = "TRACKER_TOKEN_FILE"
OAUTH_URL = "https://oauth.yandex-team.ru/authorize?..."
```

### Конвенция именования ключей и OAuth client_id

| Скилл | SERVICE_NAME | OAuth client_id |
|-------|-------------|-----------------|
| femida | `skill_store_femida` | `a09655c02a3143adb991b8debbd5fdee` |
| tracker | `skill_store_tracker` | `5f671d781aca402ab7460fde4050267b` |
| wiki | `skill_store_wiki` | `fd86e23a4d1347c1a65112f404210d46` |
| datalens | `skill_store_datalens` | `09cea1cc285845b7b4dc3f409fcacad9` |
| deepagent | `skill_store_deepagent` | `63fa6b57898e4b74a1a820c54cf144b8` |

### 3. Используйте `resolve_token()` в вашем инструменте

```python
token = resolve_token()  # автоматически: env → file → Keychain → ошибка
http = MyHTTP(token=token)
```

## Как это работает

### Цепочка поиска токена

```
1. ENV: $MY_SERVICE_TOKEN
   ↓ не найден
2. FILE: путь из $MY_SERVICE_TOKEN_FILE
   ↓ не найден
3. KEYCHAIN: macOS Keychain / Windows Credential Manager / Linux secret-tool
   ↓ не найден
4. ERROR: инструкция с командой запуска setup_token.py
```

### Платформы

| Платформа | Хранилище | Шифрование |
|-----------|-----------|------------|
| macOS | Keychain (`security` CLI) | AES-256 |
| Windows | Credential Manager (`advapi32` ctypes) | DPAPI |
| Linux | GNOME Keyring / KWallet (`secret-tool`) | зависит от DE |

### Безопасность

- **`getpass.getpass()`** — ввод токена скрыт в терминале
- **Системное хранилище** — токен зашифрован ОС, не лежит в plaintext-файлах
- **Агент не видит токен** — `resolve_token()` возвращает значение в runtime, Claude Code не логирует его
- **Fallback на env** — для CI/CD/серверов без GUI

## Файлы шаблона

| Файл | Назначение |
|------|------------|
| `template_setup_token.py` | Интерактивный TUI-скрипт установки токена |
| `template_token_auth.py` | Модуль авторизации (функции для копирования) |

## Поведение агента при ошибке

Опишите в вашем `SKILL.md`:

```markdown
## Поведение при отсутствии токена

Если инструмент вернул ошибку "Токен ... не найден":
1. НЕ проси пользователя прислать токен в чат
2. В ошибке есть готовая команда запуска терминала — выполни её
3. Предупреди: [ВАЖНО! Убедитесь что используете внутренние модели...]
4. Попроси пользователя следовать инструкциям в терминале
5. После установки — повтори исходную команду
```
