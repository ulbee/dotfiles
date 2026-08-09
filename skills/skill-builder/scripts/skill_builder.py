#!/usr/bin/env python3
"""Skill Builder — генератор скиллов для SkillStore.

Создаёт готовую структуру скилла с SKILL.md, CLI-скриптом и (опционально)
безопасной OAuth-авторизацией через системное хранилище.

stdlib-only, без внешних зависимостей.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from typing import Any


class BuilderError(RuntimeError):
    pass


# ══════════ Templates ══════════

SETUP_TOKEN_TEMPLATE = '''#!/usr/bin/env python3
"""Интерактивная установка OAuth токена для {service_display}."""

from __future__ import annotations

import getpass
import os
import platform
import subprocess
import sys

SERVICE_NAME = "{service_name}"
SERVICE_DISPLAY = "{service_display}"
OAUTH_URL = "{oauth_url}"

R = "\\033[0m"
B = "\\033[1m"
D = "\\033[2m"
GRN = "\\033[32m"
CYN = "\\033[36m"
YLW = "\\033[33m"
RED = "\\033[31m"
WHT = "\\033[97m"
BG_B = "\\033[44m"


def _enable_ansi_windows() -> None:
    if platform.system() == "Windows":
        os.system("")


def _store_info() -> tuple[str, str]:
    system = platform.system()
    if system == "Darwin":
        return "macOS Keychain", "~/Library/Keychains"
    if system == "Windows":
        return "Credential Manager", "DPAPI"
    if system == "Linux":
        return "GNOME Keyring", "libsecret"
    return "env var", "{token_env_var}"


def main() -> int:
    _enable_ansi_windows()
    store_name, store_where = _store_info()
    w = 58

    print(f"\\n  {{CYN}}{{'═' * w}}{{R}}")
    title = f"{{SERVICE_DISPLAY}} — Настройка токена"
    print(f"  {{CYN}}║{{R}}{{B}}{{BG_B}}{{WHT}}{{title:^{{w - 2}}}}{{R}}{{CYN}}║{{R}}")
    print(f"  {{CYN}}{{'═' * w}}{{R}}")
    print(f"  {{GRN}}Токен будет зашифрован в {{B}}{{store_name}}{{R}}{{GRN}} ({{store_where}}){{R}}")
    print(f"  {{CYN}}{{'─' * w}}{{R}}")

    print(f"  {{YLW}}{{B}}1.{{R}} Откройте ссылку ({{B}}Cmd+клик{{R}}):")
    print(f"  {{OAUTH_URL}}")
    print(f"  {{YLW}}{{B}}2.{{R}} Авторизуйтесь и скопируйте токен {{B}}со страницы{{R}}")
    print(f"  {{CYN}}{{'─' * w}}{{R}}")

    print(f"  {{RED}}{{B}}ВНИМАНИЕ:{{R}}{{RED}} Токен персональный. Всю ответственность{{R}}")
    print(f"  {{RED}}за действия агента с этим токеном несёте вы.{{R}}")
    print(f"  {{CYN}}{{'─' * w}}{{R}}")

    token = getpass.getpass(f"  {{B}}Вставьте токен (ввод скрыт): {{R}}").strip()
    if not token:
        print(f"  {{RED}}Токен не может быть пустым{{R}}")
        return 1

    system = platform.system()

    if system == "Darwin":
        subprocess.run(["security", "delete-generic-password", "-s", SERVICE_NAME], capture_output=True)
        r = subprocess.run(
            ["security", "add-generic-password", "-a", os.environ.get("USER", "user"),
             "-s", SERVICE_NAME, "-w", token],
            capture_output=True, text=True,
        )
        ok = r.returncode == 0
    elif system == "Windows":
        r = subprocess.run(
            ["cmdkey", f"/generic:{{SERVICE_NAME}}", "/user:oauth", f"/pass:{{token}}"],
            capture_output=True, text=True,
        )
        ok = r.returncode == 0
    elif system == "Linux":
        if subprocess.run(["which", "secret-tool"], capture_output=True).returncode != 0:
            print(f"  {{YLW}}secret-tool не найден{{R}}")
            return 1
        r = subprocess.run(
            ["secret-tool", "store", f"--label={{SERVICE_NAME}}", "service", SERVICE_NAME],
            input=token, text=True, capture_output=True,
        )
        ok = r.returncode == 0
    else:
        print(f"  {{RED}}Платформа {{system}} не поддерживается{{R}}")
        return 1

    if not ok:
        print(f"  {{RED}}{{B}}Ошибка сохранения: {{r.stderr}}{{R}}")
        return 1

    print(f"  {{CYN}}{{'─' * w}}{{R}}")
    print(f"  {{GRN}}{{B}}Токен сохранён в {{store_name}}{{R}}")
    print(f"  {{CYN}}{{'═' * w}}{{R}}")
    print(f"  {{B}}Скажите агенту: «ключ записан»{{R}}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

TOOL_TEMPLATE_AUTH = '''#!/usr/bin/env python3
"""{service_display} API tool — stdlib-only CLI."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from typing import Any
from urllib import error, parse, request

BASE_URL = "{base_url}"
API_PREFIX = "{api_prefix}"

# ── Auth constants ──
SERVICE_NAME = "{service_name}"
SERVICE_DISPLAY = "{service_display}"
TOKEN_ENV_VAR = "{token_env_var}"
TOKEN_FILE_ENV_VAR = "{token_env_var}_FILE"
OAUTH_URL = "{oauth_url}"


# ══════════ Token resolution ══════════

class TokenError(RuntimeError):
    pass


class {error_class}(RuntimeError):
    pass


def read_secret(service: str) -> str | None:
    system = platform.system()
    if system == "Darwin":
        cmd = ["security", "find-generic-password", "-s", service, "-w"]
    elif system == "Linux":
        cmd = ["secret-tool", "lookup", "service", service]
    elif system == "Windows":
        return _read_windows_credential(service)
    else:
        return None
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _read_windows_credential(target: str) -> str | None:
    try:
        import ctypes
        import ctypes.wintypes

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ("Flags", ctypes.wintypes.DWORD), ("Type", ctypes.wintypes.DWORD),
                ("TargetName", ctypes.wintypes.LPWSTR), ("Comment", ctypes.wintypes.LPWSTR),
                ("LastWritten", ctypes.wintypes.FILETIME), ("CredentialBlobSize", ctypes.wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_char)), ("Persist", ctypes.wintypes.DWORD),
                ("AttributeCount", ctypes.wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", ctypes.wintypes.LPWSTR), ("UserName", ctypes.wintypes.LPWSTR),
            ]

        pcred = ctypes.POINTER(CREDENTIAL)()
        if ctypes.windll.advapi32.CredReadW(target, 1, 0, ctypes.byref(pcred)):
            cred = pcred.contents
            blob = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
            ctypes.windll.advapi32.CredFree(pcred)
            return blob.decode("utf-16-le")
    except Exception:  # noqa: BLE001 - Windows-only, graceful fallback
        pass
    return None


def resolve_token() -> str:
    token = os.getenv(TOKEN_ENV_VAR, "").strip()
    if token:
        return token
    token_file = os.getenv(TOKEN_FILE_ENV_VAR, "").strip()
    if token_file:
        try:
            with open(token_file, "r", encoding="utf-8") as fh:
                t = fh.read().strip()
        except OSError as e:
            raise TokenError(f"Не удалось прочитать файл токена '{{token_file}}': {{e}}") from e
        if not t:
            raise TokenError(f"Файл токена '{{token_file}}' пуст")
        return t
    token = read_secret(SERVICE_NAME)
    if token:
        return token
    setup = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup_token.py")
    system = platform.system()
    terminal_cmd = f'open -a Terminal "{{setup}}"' if system == "Darwin" else f'python3 "{{setup}}"'
    raise TokenError(
        f"Токен {{SERVICE_DISPLAY}} не найден.\\n\\n"
        "[ВАЖНО! Убедитесь что используете внутренние модели в агенте "
        "прежде чем сообщать агенту токен авторизации!]\\n\\n"
        "НЕ передавайте токен в чат! Установите САМОСТОЯТЕЛЬНО.\\n\\n"
        f"Откройте терминал со скриптом установки:\\n\\n  {{terminal_cmd}}\\n\\n"
        f"Или запустите вручную:\\n\\n  python3 {{setup}}\\n\\n"
        f"Получить токен: {{OAUTH_URL}}\\n\\n"
        "После установки — повторите команду."
    )


# ══════════ HTTP client ══════════

class {http_class}:
    def __init__(self, token: str, timeout: int = 30):
        self.token = token
        self.timeout = timeout

    def _url(self, endpoint: str) -> str:
        return f"{{BASE_URL}}{{API_PREFIX}}/{{endpoint}}"

    def get(self, endpoint: str, params: dict | None = None) -> Any:
        url = self._url(endpoint)
        if params:
            url += "?" + parse.urlencode(params, doseq=True)
        req = request.Request(url, method="GET", headers={{
            "Authorization": f"OAuth {{self.token}}",
            "Accept": "application/json",
        }})
        return self._do(req)

    def post_json(self, endpoint: str, data: dict) -> Any:
        url = self._url(endpoint)
        body = json.dumps(data).encode("utf-8")
        req = request.Request(url, data=body, method="POST", headers={{
            "Authorization": f"OAuth {{self.token}}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        }})
        return self._do(req)

    def _do(self, req: request.Request) -> Any:
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                if any(m in raw[:500] for m in ("<!DOCTYPE", "<html", "passport.yandex")):
                    raise {error_class}("OAuth токен невалиден — API вернул редирект на Passport")
                return json.loads(raw) if raw.strip() else {{}}
        except error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise {error_class}(f"HTTP {{e.code}}: {{body[:500]}}") from e


# ══════════ Tools ══════════

# TODO: Реализуйте ваши инструменты здесь
# Пример:
#
# def my_tool(http: {http_class}, params: dict) -> Any:
#     """Описание инструмента."""
#     return http.get("endpoint", {{"param": params.get("param")}})


# ══════════ Registry ══════════

TOOLS: dict[str, tuple[callable, str]] = {{
    # "MyTool": (my_tool, "Описание инструмента"),
}}


def list_tools() -> dict:
    return {{"tools": [{{"name": n, "description": d}} for n, (_, d) in TOOLS.items()]}}


# ══════════ Main ══════════

def main() -> None:
    parser = argparse.ArgumentParser(description="{service_display} API CLI")
    parser.add_argument("tool", help="Tool name (e.g. ListTools)")
    parser.add_argument("--params", default="{{}}", help="JSON params string")
    parser.add_argument("--params-file", help="Path to JSON params file")
    args = parser.parse_args()

    if args.tool == "ListTools":
        print(json.dumps(list_tools(), ensure_ascii=False, indent=2))
        return

    if args.tool not in TOOLS:
        print(json.dumps({{"error": f"Unknown tool: {{args.tool}}", "available": list(TOOLS.keys())}},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    params = json.loads(args.params) if not args.params_file else json.load(open(args.params_file))

    try:
        token = resolve_token()
    except TokenError as e:
        print(json.dumps({{"error": str(e)}}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    http = {http_class}(token)
    func, _ = TOOLS[args.tool]
    try:
        result = func(http, params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except ({error_class}, TokenError) as e:
        print(json.dumps({{"error": str(e)}}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
'''

TOOL_TEMPLATE_NO_AUTH = '''#!/usr/bin/env python3
"""{service_display} tool — stdlib-only CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib import error, parse, request

BASE_URL = "{base_url}"
API_PREFIX = "{api_prefix}"


class {error_class}(RuntimeError):
    pass


# ══════════ HTTP client ══════════

class {http_class}:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def _url(self, endpoint: str) -> str:
        return f"{{BASE_URL}}{{API_PREFIX}}/{{endpoint}}"

    def get(self, endpoint: str, params: dict | None = None) -> Any:
        url = self._url(endpoint)
        if params:
            url += "?" + parse.urlencode(params, doseq=True)
        req = request.Request(url, method="GET", headers={{"Accept": "application/json"}})
        return self._do(req)

    def post_json(self, endpoint: str, data: dict) -> Any:
        url = self._url(endpoint)
        body = json.dumps(data).encode("utf-8")
        req = request.Request(url, data=body, method="POST", headers={{
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        }})
        return self._do(req)

    def _do(self, req: request.Request) -> Any:
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw.strip() else {{}}
        except error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise {error_class}(f"HTTP {{e.code}}: {{body[:500]}}") from e


# ══════════ Tools ══════════

# TODO: Реализуйте ваши инструменты здесь


# ══════════ Registry ══════════

TOOLS: dict[str, tuple[callable, str]] = {{
    # "MyTool": (my_tool, "Описание инструмента"),
}}


def list_tools() -> dict:
    return {{"tools": [{{"name": n, "description": d}} for n, (_, d) in TOOLS.items()]}}


# ══════════ Main ══════════

def main() -> None:
    parser = argparse.ArgumentParser(description="{service_display} CLI")
    parser.add_argument("tool", help="Tool name")
    parser.add_argument("--params", default="{{}}", help="JSON params string")
    parser.add_argument("--params-file", help="Path to JSON params file")
    args = parser.parse_args()

    if args.tool == "ListTools":
        print(json.dumps(list_tools(), ensure_ascii=False, indent=2))
        return

    if args.tool not in TOOLS:
        print(json.dumps({{"error": f"Unknown tool: {{args.tool}}", "available": list(TOOLS.keys())}},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    params = json.loads(args.params) if not args.params_file else json.load(open(args.params_file))

    http = {http_class}()
    func, _ = TOOLS[args.tool]
    try:
        result = func(http, params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except {error_class} as e:
        print(json.dumps({{"error": str(e)}}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
'''

SKILL_MD_TEMPLATE = '''---
name: {skill_name}
description: >
  {description}
  Триггерится на: {triggers}
---

# {display_name}

{description}

## Когда использовать

- {short_description}

## Когда не использовать

- TODO: Укажите ограничения скилла
{preconditions_section}
## Запуск

```bash
python3 scripts/{tool_filename} <ToolName> --params '{{"key":"value"}}'
python3 scripts/{tool_filename} ListTools
```

## Инструменты

- `ListTools` — список всех доступных инструментов

> После реализации инструментов обновите эту секцию через `RegenerateSkillMD`.

## Быстрые примеры

```bash
# Список инструментов
python3 scripts/{tool_filename} ListTools
```

> После реализации добавьте примеры через `RegenerateSkillMD`.
{token_error_section}
## Installation

Этот скилл — директория с файлами SKILL.md + scripts/.
Для установки скопируй всю директорию в нужное место.

### Определи куда ставить

| Агент | Проверь существование | Куда ставить |
|-------|----------------------|-------------|
| **Claude Code** | `~/.claude/skills/` | `~/.claude/skills/{skill_name}/` |
| **Cursor** | `~/.cursor/skills/` | `~/.cursor/skills/{skill_name}/` |
| **Codex** | `~/.codex/` или `~/.agents/` | `~/.agents/skills/{skill_name}/` |
| **Другой агент** | ничего из вышеперечисленного | `~/.ai-skills/{skill_name}/` |

### Шаги установки

1. Определи агента (проверь какие директории из таблицы выше существуют)
2. Скопируй директорию `{skill_name}/` (содержащую этот SKILL.md + scripts/) в путь из таблицы
3. Проверь: `python3 <путь_установки>/scripts/{tool_filename} ListTools`

### ВАЖНО: НЕ использовать

- `claude plugin install` — это другой механизм, скилл так НЕ ставится
- Не нужно создавать `plugin.json`, `package.json` или любые конфиг-файлы
- Установка = просто копирование директории в правильное место
'''

PRECONDITIONS_AUTH = '''
## Preconditions

Токен ищется автоматически:
1. Переменная окружения `{token_env_var}`
2. Файл по пути из `{token_env_var}_FILE`
3. Системное хранилище (macOS Keychain / Windows / Linux) — сервис `{service_name}`

Рекомендуемый способ — сохранить токен в системное хранилище:
```bash
python3 scripts/setup_token.py
```
'''

PRECONDITIONS_NO_AUTH = '''
## Preconditions

Скилл не требует авторизации.
'''

TOKEN_ERROR_SECTION = '''
## Поведение при отсутствии токена

Если инструмент вернул ошибку "Токен ... не найден":
1. НЕ проси пользователя прислать токен в чат
2. В ошибке есть готовая команда запуска терминала — выполни её
3. Предупреди: [ВАЖНО! Убедитесь что используете внутренние модели в агенте]
4. Попроси пользователя следовать инструкциям в терминале
5. После установки — повтори исходную команду
'''


# ══════════ Tools ══════════

def _slugify(name: str) -> str:
    """Convert name to slug: lowercase, replace spaces/underscores with hyphens."""
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9а-яё\s_-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    return re.sub(r'-+', '-', s).strip('-')


def _class_name(name: str) -> str:
    """Convert name to PascalCase class name."""
    return ''.join(w.capitalize() for w in re.split(r'[\s_-]+', name) if w)


def scaffold(params: dict) -> dict:
    """Создать каркас скилла."""
    skill_name = params.get("skill_name", "")
    display_name = params.get("display_name", "")
    description = params.get("description", "")
    output_dir = params.get("output_dir", "/tmp")
    with_auth = params.get("with_auth", False)

    if not skill_name:
        raise BuilderError("Параметр 'skill_name' обязателен (латиница, дефисы: my-awesome-tool)")
    if not display_name:
        raise BuilderError("Параметр 'display_name' обязателен (напр. 'My Awesome Tool')")
    if not description:
        raise BuilderError("Параметр 'description' обязателен")

    slug = _slugify(skill_name)
    cls = _class_name(skill_name)
    tool_filename = f"{slug.replace('-', '_')}_tool.py"

    skill_dir = os.path.join(output_dir, slug)
    scripts_dir = os.path.join(skill_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)

    created_files = []

    # Auth-specific params
    base_url = params.get("base_url", "https://example.yandex-team.ru")
    api_prefix = params.get("api_prefix", "/v1")
    service_name = params.get("service_name", f"skill_store_{slug.replace('-', '_')}")
    token_env_var = params.get("token_env_var", f"{slug.replace('-', '_').upper()}_TOKEN")
    oauth_url = params.get("oauth_url", "https://oauth.yandex-team.ru/authorize?response_type=token&client_id=YOUR_CLIENT_ID")
    oauth_client_id = params.get("oauth_client_id", "")
    if oauth_client_id:
        oauth_url = f"https://oauth.yandex-team.ru/authorize?response_type=token&client_id={oauth_client_id}"

    triggers = params.get("triggers", f'"{slug}", "{display_name.lower()}"')
    short_description = params.get("short_description", description)

    template_vars = {
        "skill_name": slug,
        "display_name": display_name,
        "service_display": display_name,
        "description": description,
        "short_description": short_description,
        "triggers": triggers,
        "tool_filename": tool_filename,
        "base_url": base_url,
        "api_prefix": api_prefix,
        "service_name": service_name,
        "token_env_var": token_env_var,
        "oauth_url": oauth_url,
        "error_class": f"{cls}Error",
        "http_class": f"{cls}HTTP",
    }

    # Generate tool script
    if with_auth:
        tool_content = TOOL_TEMPLATE_AUTH.format(**template_vars)
        template_vars["preconditions_section"] = PRECONDITIONS_AUTH.format(**template_vars)
        template_vars["token_error_section"] = TOKEN_ERROR_SECTION
    else:
        tool_content = TOOL_TEMPLATE_NO_AUTH.format(**template_vars)
        template_vars["preconditions_section"] = PRECONDITIONS_NO_AUTH
        template_vars["token_error_section"] = ""

    tool_path = os.path.join(scripts_dir, tool_filename)
    with open(tool_path, "w", encoding="utf-8") as f:
        f.write(tool_content)
    created_files.append(f"scripts/{tool_filename}")

    # Generate setup_token.py if auth
    if with_auth:
        setup_content = SETUP_TOKEN_TEMPLATE.format(**template_vars)
        setup_path = os.path.join(scripts_dir, "setup_token.py")
        with open(setup_path, "w", encoding="utf-8") as f:
            f.write(setup_content)
        created_files.append("scripts/setup_token.py")

    # Generate SKILL.md
    skill_md = SKILL_MD_TEMPLATE.format(**template_vars)
    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    with open(skill_md_path, "w", encoding="utf-8") as f:
        f.write(skill_md)
    created_files.append("SKILL.md")

    return {
        "skill_dir": skill_dir,
        "slug": slug,
        "files": created_files,
        "with_auth": with_auth,
        "next_steps": [
            f"1. Откройте {tool_path} и реализуйте инструменты в секции Tools",
            f"2. Заполните TOOLS dict в секции Registry",
            f"3. Обновите SKILL.md — секции 'Инструменты' и 'Быстрые примеры'",
            f"4. Проверьте: python3 {tool_path} ListTools",
            f"5. Загрузите в SkillStore через CreateSkill",
        ],
    }


def validate(params: dict) -> dict:
    """Проверить скилл по чеклисту."""
    skill_dir = params.get("skill_dir", "")
    if not skill_dir:
        raise BuilderError("Параметр 'skill_dir' обязателен")
    if not os.path.isdir(skill_dir):
        raise BuilderError(f"Директория не найдена: {skill_dir}")

    checks = []
    has_errors = False

    # SKILL.md exists
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if os.path.isfile(skill_md):
        checks.append({"check": "SKILL.md существует", "status": "ok"})
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()

        # YAML frontmatter
        if content.startswith("---"):
            checks.append({"check": "YAML frontmatter", "status": "ok"})
            if "name:" in content[:500]:
                checks.append({"check": "name: в YAML", "status": "ok"})
            else:
                checks.append({"check": "name: в YAML", "status": "error", "detail": "Отсутствует поле name:"})
                has_errors = True
            if "description:" in content[:500]:
                checks.append({"check": "description: в YAML", "status": "ok"})
            else:
                checks.append({"check": "description: в YAML", "status": "error", "detail": "Отсутствует поле description:"})
                has_errors = True
        else:
            checks.append({"check": "YAML frontmatter", "status": "error", "detail": "Файл не начинается с ---"})
            has_errors = True

        # Installation section
        if "## Installation" in content:
            checks.append({"check": "Секция Installation", "status": "ok"})
        else:
            checks.append({"check": "Секция Installation", "status": "error", "detail": "Без этой секции скилл не установится"})
            has_errors = True

        # No hardcoded paths
        home = os.path.expanduser("~")
        if home in content and "/Users/" in content:
            checks.append({"check": "Нет захардкоженных путей", "status": "warning", "detail": f"Найден абсолютный путь {home}"})
        else:
            checks.append({"check": "Нет захардкоженных путей", "status": "ok"})

        # Triggers
        if "Триггерится на:" in content:
            checks.append({"check": "Триггер-фразы", "status": "ok"})
        else:
            checks.append({"check": "Триггер-фразы", "status": "warning", "detail": "Рекомендуется добавить триггер-фразы"})
    else:
        checks.append({"check": "SKILL.md существует", "status": "error", "detail": "Файл не найден"})
        has_errors = True

    # Scripts directory
    scripts_dir = os.path.join(skill_dir, "scripts")
    if os.path.isdir(scripts_dir):
        checks.append({"check": "Директория scripts/", "status": "ok"})
        py_files = [f for f in os.listdir(scripts_dir) if f.endswith(".py")]
        if py_files:
            checks.append({"check": f"Python-скрипты: {', '.join(py_files)}", "status": "ok"})
            for pf in py_files:
                path = os.path.join(scripts_dir, pf)
                with open(path, "r", encoding="utf-8") as f:
                    src = f.read()
                if src.startswith("#!/usr/bin/env python3"):
                    checks.append({"check": f"{pf}: shebang", "status": "ok"})
                else:
                    checks.append({"check": f"{pf}: shebang", "status": "warning", "detail": "Рекомендуется #!/usr/bin/env python3"})

                # Check for external deps
                externals = []
                for line in src.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("import ") or stripped.startswith("from "):
                        for ext in ("requests", "httpx", "aiohttp", "click", "typer", "rich"):
                            if ext in stripped:
                                externals.append(ext)
                if externals:
                    checks.append({"check": f"{pf}: stdlib-only", "status": "error", "detail": f"Внешние зависимости: {', '.join(externals)}"})
                    has_errors = True
                else:
                    checks.append({"check": f"{pf}: stdlib-only", "status": "ok"})
        else:
            checks.append({"check": "Python-скрипты", "status": "warning", "detail": "Нет .py файлов в scripts/"})

        # Check for missing file references in shell scripts
        sh_files = [f for f in os.listdir(scripts_dir) if f.endswith(".sh")]
        for shf in sh_files:
            path = os.path.join(scripts_dir, shf)
            with open(path, "r", encoding="utf-8") as f:
                sh_src = f.read()
            # Find references to sibling scripts: $(dirname "$0")/something.sh, SCRIPT_DIR/something
            import re as _re
            refs = _re.findall(r'(?:dirname\s+["\$0"\']+\)|SCRIPT_DIR)[/"]([a-zA-Z0-9_.-]+\.(?:sh|py))', sh_src)
            # Also find: source ./something.sh, . ./something.sh
            refs += _re.findall(r'(?:source|\.)\s+["\']?(?:\./)?([a-zA-Z0-9_.-]+\.sh)', sh_src)
            missing_refs = [r for r in set(refs) if not os.path.isfile(os.path.join(scripts_dir, r))]
            if missing_refs:
                checks.append({
                    "check": f"{shf}: зависимости от соседних файлов",
                    "status": "error",
                    "detail": f"Файлы не найдены в scripts/: {', '.join(missing_refs)}",
                })
                has_errors = True
            elif refs:
                checks.append({"check": f"{shf}: зависимости от соседних файлов", "status": "ok"})

        # Functional smoke-test: try running ListTools or --help
        main_scripts = [f for f in (py_files if 'py_files' in dir() else []) if "tool" in f.lower() or "cli" in f.lower()]
        if not main_scripts:
            main_scripts = py_files if 'py_files' in dir() else []
        for ms in main_scripts[:1]:  # test only the first main script
            ms_path = os.path.join(scripts_dir, ms)
            import subprocess as _sp
            try:
                r = _sp.run(
                    [sys.executable, ms_path, "ListTools", "--params", "{}"],
                    capture_output=True, text=True, timeout=10,
                    cwd=scripts_dir,
                )
                if r.returncode == 0 and r.stdout.strip():
                    checks.append({"check": f"{ms}: smoke-test (ListTools)", "status": "ok"})
                else:
                    # Try --help fallback
                    r2 = _sp.run(
                        [sys.executable, ms_path, "--help"],
                        capture_output=True, text=True, timeout=5,
                        cwd=scripts_dir,
                    )
                    if r2.returncode == 0:
                        checks.append({"check": f"{ms}: smoke-test (--help)", "status": "ok"})
                    else:
                        detail = (r.stderr.strip() or r2.stderr.strip() or "Exit code non-zero")[:200]
                        checks.append({"check": f"{ms}: smoke-test", "status": "warning", "detail": f"Скрипт не отвечает: {detail}"})
            except _sp.TimeoutExpired:
                checks.append({"check": f"{ms}: smoke-test", "status": "warning", "detail": "Timeout 10s"})
            except Exception as e:  # noqa: BLE001 - validation resilience
                checks.append({"check": f"{ms}: smoke-test", "status": "warning", "detail": str(e)[:200]})
    else:
        checks.append({"check": "Директория scripts/", "status": "warning", "detail": "Нет директории scripts/"})

    errors = sum(1 for c in checks if c["status"] == "error")
    warnings = sum(1 for c in checks if c["status"] == "warning")

    return {
        "valid": not has_errors,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def list_templates(_params: dict) -> dict:
    """Показать доступные шаблоны."""
    return {
        "templates": [
            {
                "name": "basic",
                "description": "Скилл без авторизации — простой HTTP-клиент",
                "params": "skill_name, display_name, description, base_url, api_prefix",
                "usage": '{"skill_name":"my-tool","display_name":"My Tool","description":"...","base_url":"https://api.example.com","api_prefix":"/v1"}',
            },
            {
                "name": "oauth",
                "description": "Скилл с OAuth-авторизацией через Keychain (Yandex-паттерн)",
                "params": "skill_name, display_name, description, base_url, api_prefix, oauth_client_id, service_name",
                "usage": '{"skill_name":"my-tool","display_name":"My Tool","description":"...","base_url":"https://api.yandex-team.ru","api_prefix":"/v3","with_auth":true,"oauth_client_id":"abc123"}',
            },
        ],
        "workflow": [
            "1. [DeepAgent] Используй скилл DeepAgent из SkillStore для поиска документации по API",
            "2. [Scaffold] Создай каркас скилла через Scaffold или ScaffoldWithAuth",
            "3. [Code] Реализуй инструменты в сгенерированном *_tool.py",
            "4. [RegenerateSkillMD] Обнови SKILL.md из кода — секции Инструменты и Примеры",
            "5. [Validate] Проверь скилл через Validate",
            "6. [SkillStore] Загрузи в каталог через SkillStore Tool (CreateSkill)",
        ],
    }


def scaffold_with_auth(params: dict) -> dict:
    """Создать каркас скилла с OAuth-авторизацией."""
    params["with_auth"] = True
    required = ["oauth_client_id", "base_url"]
    missing = [k for k in required if not params.get(k)]
    if missing:
        raise BuilderError(
            f"Для скилла с авторизацией обязательны: {', '.join(missing)}. "
            "OAuth client_id можно получить на https://oauth.yandex-team.ru/"
        )
    return scaffold(params)


def _extract_tools_from_code(code: str) -> list[tuple[str, str]]:
    """Извлечь имена и описания инструментов из TOOLS dict в исходном коде.

    Парсит AST, ищет присваивание TOOLS = { "Name": (func, "description"), ... }.
    Возвращает список (name, description).
    """
    tools = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return tools

    for node in ast.walk(tree):
        # Обрабатываем и TOOLS = {} (Assign) и TOOLS: type = {} (AnnAssign)
        target_name = None
        value_node = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TOOLS":
                    target_name = target.id
                    value_node = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "TOOLS" and node.value:
                target_name = node.target.id
                value_node = node.value

        if not target_name or not isinstance(value_node, ast.Dict):
            continue

        for key, value in zip(value_node.keys, value_node.values):
            name = ""
            desc = ""
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                name = key.value
            if isinstance(value, ast.Tuple) and len(value.elts) >= 2:
                desc_node = value.elts[1]
                if isinstance(desc_node, ast.Constant) and isinstance(desc_node.value, str):
                    desc = desc_node.value
            if name:
                tools.append((name, desc))
    return tools


def regenerate_skill_md(params: dict) -> dict:
    """Перегенерировать секции 'Инструменты' и 'Быстрые примеры' в SKILL.md из кода."""
    skill_dir = params.get("skill_dir", "")
    if not skill_dir:
        raise BuilderError("Параметр 'skill_dir' обязателен")
    if not os.path.isdir(skill_dir):
        raise BuilderError(f"Директория не найдена: {skill_dir}")

    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md_path):
        raise BuilderError(f"SKILL.md не найден в {skill_dir}")

    # Найти *_tool.py в scripts/
    scripts_dir = os.path.join(skill_dir, "scripts")
    tool_files = []
    if os.path.isdir(scripts_dir):
        tool_files = [f for f in os.listdir(scripts_dir)
                      if f.endswith("_tool.py") or f.endswith("_tool.py")]

    if not tool_files:
        raise BuilderError(f"Не найдены *_tool.py в {scripts_dir}")

    # Собрать инструменты из всех tool-файлов
    all_tools = []
    tool_filename = tool_files[0]
    for tf in tool_files:
        path = os.path.join(scripts_dir, tf)
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        extracted = _extract_tools_from_code(code)
        all_tools.extend(extracted)
        if extracted:
            tool_filename = tf

    if not all_tools:
        raise BuilderError(
            "Не удалось извлечь инструменты из TOOLS dict. "
            "Убедитесь что TOOLS = {\"Name\": (func, \"описание\")} определён в коде."
        )

    # Генерируем секцию "Инструменты"
    tools_lines = []
    for name, desc in all_tools:
        tools_lines.append(f"- `{name}` — {desc}" if desc else f"- `{name}`")
    tools_lines.append(f"- `ListTools` — список всех доступных инструментов")
    tools_section = "\n".join(tools_lines)

    # Генерируем секцию "Быстрые примеры"
    examples_lines = ["```bash"]
    for name, desc in all_tools[:3]:  # Первые 3 инструмента как примеры
        comment = desc.split('.')[0] if desc else name
        examples_lines.append(f"# {comment}")
        examples_lines.append(f"python3 scripts/{tool_filename} {name} --params '{{}}'\n")
    examples_lines.append(f"# Список инструментов")
    examples_lines.append(f"python3 scripts/{tool_filename} ListTools")
    examples_lines.append("```")
    examples_section = "\n".join(examples_lines)

    # Прочитать и обновить SKILL.md
    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Заменить секцию "## Инструменты" до следующего "##"
    content = re.sub(
        r'(## Инструменты\n\n).*?(?=\n## )',
        rf'\1{tools_section}\n',
        content,
        flags=re.DOTALL,
    )

    # Заменить секцию "## Быстрые примеры" до следующего "##"
    content = re.sub(
        r'(## Быстрые примеры\n\n).*?(?=\n## )',
        rf'\1{examples_section}\n',
        content,
        flags=re.DOTALL,
    )

    # Если "Быстрые примеры" — последняя секция перед Installation или концом файла
    if "## Быстрые примеры" in content and re.search(r'## Быстрые примеры\n\n.*?TODO', content, re.DOTALL):
        content = re.sub(
            r'(## Быстрые примеры\n\n).*?(?=\n## |$)',
            rf'\1{examples_section}\n',
            content,
            flags=re.DOTALL,
        )

    with open(skill_md_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "updated": skill_md_path,
        "tools_found": len(all_tools),
        "tools": [{"name": n, "description": d} for n, d in all_tools],
        "tool_file": tool_filename,
    }


# ══════════ Registry ══════════

TOOLS: dict[str, tuple[callable, str]] = {
    "Scaffold": (scaffold, "Создать каркас скилла без авторизации"),
    "ScaffoldWithAuth": (scaffold_with_auth, "Создать каркас скилла с OAuth через Keychain"),
    "Validate": (validate, "Проверить скилл по чеклисту перед загрузкой"),
    "RegenerateSkillMD": (regenerate_skill_md, "Перегенерировать SKILL.md из кода скрипта"),
    "ListTemplates": (list_templates, "Показать доступные шаблоны и workflow"),
}


def list_tools() -> dict:
    return {"tools": [{"name": n, "description": d} for n, (_, d) in TOOLS.items()]}


# ══════════ Main ══════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Skill Builder — генератор скиллов для SkillStore")
    parser.add_argument("tool", help="Tool name (Scaffold, ScaffoldWithAuth, Validate, ListTemplates, ListTools)")
    parser.add_argument("--params", default="{}", help="JSON params string")
    parser.add_argument("--params-file", help="Path to JSON params file")
    args = parser.parse_args()

    if args.tool == "ListTools":
        print(json.dumps(list_tools(), ensure_ascii=False, indent=2))
        return

    if args.tool not in TOOLS:
        print(json.dumps({"error": f"Unknown tool: {args.tool}", "available": list(TOOLS.keys())},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    params = json.loads(args.params) if not args.params_file else json.load(open(args.params_file))

    func, _ = TOOLS[args.tool]
    try:
        result = func(params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except BuilderError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
