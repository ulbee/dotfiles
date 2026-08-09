#!/usr/bin/env python3
"""
Шаблон: интерактивная установка OAuth токена в системное хранилище.

Для создания скрипта установки токена в своём скилле:
1. Скопируйте этот файл в scripts/setup_token.py
2. Замените константы ниже на свои значения
3. Готово — скрипт сам определит платформу и сохранит токен
"""

from __future__ import annotations

import getpass
import os
import platform
import subprocess
import sys

# ══════════════════════════════════════════════════════
#  НАСТРОЙТЕ ЭТИ КОНСТАНТЫ ПОД СВОЙ СЕРВИС
# ══════════════════════════════════════════════════════

SERVICE_NAME = "skill_store_my_service"  # Имя в Keychain (префикс skill_store_)
SERVICE_DISPLAY = "My Service"           # Отображаемое название в TUI
OAUTH_URL = "https://oauth.yandex-team.ru/authorize?response_type=token&client_id=YOUR_CLIENT_ID"

# ══════════════════════════════════════════════════════

# ANSI colors
R = "\033[0m"
B = "\033[1m"
D = "\033[2m"
GRN = "\033[32m"
CYN = "\033[36m"
YLW = "\033[33m"
RED = "\033[31m"
WHT = "\033[97m"
BG_B = "\033[44m"


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
    return "env var", f"{SERVICE_NAME.upper().replace('-', '_')}_TOKEN"


def _install_secret_tool() -> None:
    """Установить secret-tool через доступный пакетный менеджер Linux."""
    managers = [
        (["apt-get", "install", "-y", "libsecret-tools"], "apt-get"),
        (["dnf", "install", "-y", "libsecret"], "dnf"),
        (["yum", "install", "-y", "libsecret"], "yum"),
        (["pacman", "-S", "--noconfirm", "libsecret"], "pacman"),
        (["zypper", "install", "-y", "libsecret-tools"], "zypper"),
    ]
    for cmd, name in managers:
        if subprocess.run(["which", name], capture_output=True).returncode == 0:
            print(f"  {D}Пакетный менеджер: {name}{R}")
            subprocess.run(["sudo"] + cmd)
            return
    print(f"  {RED}Не найден пакетный менеджер. Установите libsecret-tools вручную.{R}")


def main() -> int:
    _enable_ansi_windows()
    store_name, store_where = _store_info()
    w = 58

    # === Header ===
    print(f"\n  {CYN}{'═' * w}{R}")
    title = f"{SERVICE_DISPLAY} — Настройка токена"
    print(f"  {CYN}║{R}{B}{BG_B}{WHT}{title:^{w - 2}}{R}{CYN}║{R}")
    print(f"  {CYN}{'═' * w}{R}")
    print(f"  {GRN}Токен будет зашифрован в {B}{store_name}{R}{GRN} ({store_where}){R}")
    print(f"  {CYN}{'─' * w}{R}")

    # === Steps ===
    print(f"  {YLW}{B}1.{R} Откройте ссылку ({B}Cmd+клик{R}):")
    print(f"  {OAUTH_URL}")
    print(f"  {YLW}{B}2.{R} Авторизуйтесь и скопируйте токен {B}со страницы{R}")
    print(f"  {CYN}{'─' * w}{R}")

    # === Warning ===
    print(f"  {RED}{B}ВНИМАНИЕ:{R}{RED} Токен персональный. Всю ответственность{R}")
    print(f"  {RED}за действия агента с этим токеном несёте вы.{R}")
    print(f"  {CYN}{'─' * w}{R}")

    # === Input ===
    token = getpass.getpass(f"  {B}Вставьте токен (ввод скрыт): {R}").strip()
    if not token:
        print(f"  {RED}Токен не может быть пустым{R}")
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
            ["cmdkey", f"/generic:{SERVICE_NAME}", "/user:oauth", f"/pass:{token}"],
            capture_output=True, text=True,
        )
        ok = r.returncode == 0

    elif system == "Linux":
        if subprocess.run(["which", "secret-tool"], capture_output=True).returncode != 0:
            print(f"  {YLW}secret-tool не найден, устанавливаю...{R}")
            _install_secret_tool()
        r = subprocess.run(
            ["secret-tool", "store", f"--label={SERVICE_NAME}", "service", SERVICE_NAME],
            input=token, text=True, capture_output=True,
        )
        ok = r.returncode == 0

    else:
        print(f"  {RED}Платформа {system} не поддерживается{R}")
        return 1

    if not ok:
        print(f"  {RED}{B}Ошибка сохранения: {r.stderr}{R}")
        return 1

    # === Verification ===
    verified = None
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, scripts_dir)
    try:
        from template_token_auth import read_secret
        verified = bool(read_secret(SERVICE_NAME))
    except ImportError:
        pass

    # === Result ===
    print(f"  {CYN}{'─' * w}{R}")
    print(f"  {GRN}{B}Токен сохранён в {store_name}{R}")
    if verified is True:
        print(f"  {GRN}Верификация пройдена{R}")
    elif verified is False:
        print(f"  {YLW}Верификация не удалась — проверьте вручную{R}")
    print(f"  {CYN}{'═' * w}{R}")
    print(f"  {B}Скажите агенту: «ключ записан»{R}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
