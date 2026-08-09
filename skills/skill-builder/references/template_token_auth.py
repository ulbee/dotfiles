"""
Шаблон: кроссплатформенная безопасная авторизация через системное хранилище.

Для использования в своём скилле:
1. Скопируйте функции из этого файла в свой *_tool.py
2. Замените константы ниже на свои значения
3. Вызывайте resolve_token() для получения токена

Цепочка приоритетов:
  env var → token file → системное хранилище (Keychain/CredMan/secret-tool) → ошибка
"""

from __future__ import annotations

import os
import platform

# ══════════════════════════════════════════════════════
#  НАСТРОЙТЕ ЭТИ КОНСТАНТЫ ПОД СВОЙ СЕРВИС
# ══════════════════════════════════════════════════════

SERVICE_NAME = "skill_store_my_service"         # Имя в Keychain (префикс skill_store_)
SERVICE_DISPLAY = "My Service"                 # Отображаемое название
TOKEN_ENV_VAR = "MY_SERVICE_TOKEN"             # Переменная окружения с токеном
TOKEN_FILE_ENV_VAR = "MY_SERVICE_TOKEN_FILE"   # Переменная с путём к файлу
OAUTH_URL = "https://oauth.yandex-team.ru/authorize?response_type=token&client_id=YOUR_CLIENT_ID"

# ══════════════════════════════════════════════════════


class TokenError(RuntimeError):
    """Ошибка авторизации — токен не найден или невалиден."""


def read_secret(service: str) -> str | None:
    """Кроссплатформенное чтение из системного хранилища секретов."""
    import subprocess

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
    """Чтение из Windows Credential Manager через ctypes (stdlib-only)."""
    try:
        import ctypes
        import ctypes.wintypes

        CRED_TYPE_GENERIC = 1

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ("Flags", ctypes.wintypes.DWORD),
                ("Type", ctypes.wintypes.DWORD),
                ("TargetName", ctypes.wintypes.LPWSTR),
                ("Comment", ctypes.wintypes.LPWSTR),
                ("LastWritten", ctypes.wintypes.FILETIME),
                ("CredentialBlobSize", ctypes.wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
                ("Persist", ctypes.wintypes.DWORD),
                ("AttributeCount", ctypes.wintypes.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", ctypes.wintypes.LPWSTR),
                ("UserName", ctypes.wintypes.LPWSTR),
            ]

        pcred = ctypes.POINTER(CREDENTIAL)()
        advapi32 = ctypes.windll.advapi32
        if advapi32.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(pcred)):
            cred = pcred.contents
            blob = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
            advapi32.CredFree(pcred)
            return blob.decode("utf-16-le")
    except Exception:  # noqa: BLE001 - Windows-only, graceful fallback
        pass
    return None


def open_terminal_command(setup_script: str) -> str:
    """Команда для открытия нового терминала со скриптом установки."""
    system = platform.system()
    if system == "Darwin":
        return f'open -a Terminal "{setup_script}"'
    if system == "Linux":
        return f'gnome-terminal -- python3 "{setup_script}" || xterm -e python3 "{setup_script}"'
    if system == "Windows":
        return f'start cmd /c python3 "{setup_script}"'
    return f'python3 "{setup_script}"'


def token_not_found_message() -> str:
    """Сообщение об ошибке с инструкцией по установке токена."""
    setup_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup_token.py")
    terminal_cmd = open_terminal_command(setup_script)
    return (
        f"Токен {SERVICE_DISPLAY} не найден.\n\n"
        "[ВАЖНО! Убедитесь что используете внутренние модели в агенте "
        "прежде чем сообщать агенту токен авторизации!]\n\n"
        "НЕ передавайте токен в чат! Установите САМОСТОЯТЕЛЬНО.\n\n"
        f"Откройте терминал со скриптом установки:\n\n  {terminal_cmd}\n\n"
        f"Или запустите вручную:\n\n  python3 {setup_script}\n\n"
        f"Получить токен: {OAUTH_URL}\n\n"
        "После установки — повторите команду."
    )


def _load_token_from_file(path: str) -> str:
    """Загрузить токен из файла."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            token = fh.read().strip()
    except OSError as e:
        raise TokenError(f"Не удалось прочитать файл токена '{path}': {e}") from e
    if not token:
        raise TokenError(f"Файл токена '{path}' пуст")
    return token


def resolve_token() -> str:
    """
    Получить токен из первого доступного источника:
    1. Переменная окружения TOKEN_ENV_VAR
    2. Файл по пути из TOKEN_FILE_ENV_VAR
    3. Системное хранилище секретов (Keychain / Credential Manager / secret-tool)
    4. Ошибка с инструкцией
    """
    token = os.getenv(TOKEN_ENV_VAR, "").strip()
    if token:
        return token

    token_file = os.getenv(TOKEN_FILE_ENV_VAR, "").strip()
    if token_file:
        return _load_token_from_file(token_file)

    token = read_secret(SERVICE_NAME)
    if token:
        return token

    raise TokenError(token_not_found_message())


def check_html_auth_error(response_text: str) -> None:
    """Проверить, не вернул ли API редирект на Passport вместо JSON."""
    if any(marker in response_text[:500] for marker in ("<!DOCTYPE", "<html", "passport.yandex")):
        raise TokenError(
            f"OAuth токен {SERVICE_DISPLAY} невалиден или истёк — "
            "API вернул редирект на Passport"
        )
