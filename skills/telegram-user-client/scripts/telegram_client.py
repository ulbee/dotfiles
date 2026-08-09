#!/usr/bin/env python3
"""
Telegram User Client — работает через StringSession.
Загружает сессию из .string_session файла.
"""
import sys, asyncio, os
sys.path.insert(0, '/workspace/skills/telegram-user-client/deps')

import argparse
from telethon import TelegramClient
from telethon.sessions.string import StringSession
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
STRING_FILE = os.path.join(SKILL_DIR, ".string_session")
ENV_FILE = os.path.join(SKILL_DIR, ".env")

API_ID = 32392342
API_HASH = "82c00720c94d64dcc8e2f147a71a2f99"

def load_string_session():
    with open(STRING_FILE) as f:
        return f.read().strip()

async def cmd_connect():
    string = load_string_session()
    client = TelegramClient(StringSession(string), API_ID, API_HASH)
    await client.connect()
    me = await client.get_me()
    return f"✅ Подключено! {me.first_name} {me.last_name or ''} (@{me.username})"

async def cmd_list_chats(limit=20):
    string = load_string_session()
    client = TelegramClient(StringSession(string), API_ID, API_HASH)
    await client.connect()
    result = await client(GetDialogsRequest(
        offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(),
        limit=limit, hash=0
    ))
    lines = ["📋 Чаты:"]
    for d in result.dialogs[:limit]:
        entity = await client.get_entity(d.peer)
        name = getattr(entity, 'first_name', '') or getattr(entity, 'title', '???')
        username = getattr(entity, 'username', '')
        uid = getattr(d.peer, 'user_id', 0) or getattr(d.peer, 'chat_id', 0) or 0
        kind = "👤" if hasattr(d.peer, 'user_id') else "💬" if hasattr(d.peer, 'chat_id') else "📢"
        u = f" (@{username})" if username else ""
        lines.append(f"  {kind} [{uid}] {name}{u}")
    await client.disconnect()
    return "\n".join(lines)

async def cmd_read_chat(chat_id, limit=10):
    string = load_string_session()
    client = TelegramClient(StringSession(string), API_ID, API_HASH)
    await client.connect()
    entity = await client.get_entity(int(chat_id))
    msgs = await client.get_messages(entity, limit=int(limit))
    lines = [f"💬 Последние {len(msgs)} сообщений:"]
    for m in reversed(msgs):
        sender = "???"
        if m.from_id and hasattr(m.from_id, 'user_id'):
            try:
                u = await client.get_entity(m.from_id.user_id)
                sender = f"@{u.username}" if u.username else (u.first_name or "???")
            except Exception:
                sender = str(m.from_id.user_id)
        text = m.text or "(медиа)"
        lines.append(f"[{m.id}] {sender}: {text[:100]}")
    await client.disconnect()
    return "\n".join(lines)

async def cmd_send_message(chat_id, text):
    string = load_string_session()
    client = TelegramClient(StringSession(string), API_ID, API_HASH)
    await client.connect()
    entity = await client.get_entity(int(chat_id))
    msg = await client.send_message(entity, text)
    await client.disconnect()
    return f"✅ Отправлено! ID: {msg.id}"

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["connect", "list-chats", "read-chat", "send-message"])
    parser.add_argument("args", nargs="*")
    args = parser.parse_args()

    kwargs = {}
    if args.cmd == "read-chat":
        kwargs = {"chat_id": args.args[0], "limit": int(args.args[1]) if len(args.args) > 1 else 10}
    elif args.cmd == "send-message":
        kwargs = {"chat_id": args.args[0], "text": " ".join(args.args[1:])}

    fns = {"connect": cmd_connect, "list-chats": cmd_list_chats, "read-chat": cmd_read_chat, "send-message": cmd_send_message}
    result = await fns[args.cmd](**kwargs)
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
