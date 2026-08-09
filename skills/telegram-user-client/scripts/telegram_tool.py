#!/usr/bin/env python3
"""
Telegram tool — обёртка для OpenClaw агента.
Принимает JSON-команды из stdin, выполняет, возвращает JSON в stdout.
"""

import sys
import json
import asyncio
import os
import argparse

# Добавляем путь к telegram_client
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_client import (
    cmd_connect,
    cmd_disconnect,
    cmd_list_chats,
    cmd_read_chat,
    cmd_send_message,
    cmd_reply_to,
)


COMMANDS = {
    "connect": cmd_connect,
    "disconnect": cmd_disconnect,
    "list-chats": cmd_list_chats,
    "read-chat": cmd_read_chat,
    "send-message": cmd_send_message,
    "reply-to": cmd_reply_to,
}


async def run_command(cmd: str, params: dict) -> dict:
    """Execute a command and return a JSON-serializable result."""
    if cmd not in COMMANDS:
        return {"ok": False, "error": f"Unknown command: {cmd}"}

    try:
        fn = COMMANDS[cmd]
        # Extract expected params
        result = await fn(**params)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    # Читаем JSON из аргументов или stdin
    if len(sys.argv) > 1:
        # Всё в one-liner: telegram_tool.py '{"cmd":"connect","params":{}}'
        input_data = json.loads(sys.argv[1])
    else:
        input_data = json.load(sys.stdin)

    cmd = input_data.get("cmd", "")
    params = input_data.get("params", {})

    async def run():
        result = await run_command(cmd, params)
        print(json.dumps(result, ensure_ascii=False))

    asyncio.run(run())


if __name__ == "__main__":
    main()
