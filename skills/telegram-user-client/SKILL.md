---
name: telegram-user-client
description: Читает и отвечает в чатах Telegram от лица пользователя через Telethon.
version: "1.0.0"
---

# Telegram User Client (Telethon)

Подключается к Telegram от имени пользователя (не бота) через библиотеку Telethon.

## Возможности

- Подключение к Telegram via MTProto (user session)
- Чтение последних сообщений из любых чатов
- Отправка сообщений от лица пользователя
- Скачивание файлов и документов

## Установка зависимостей

```bash
cd /путь/к/скиллу
pip install telethon python-dotenv --target=./scripts/deps
```

## Настройка

1. Получи credentials на https://my.telegram.org → API development tools
2. Создай `.env` на основе `.env.example`
3. Запусти `python3 scripts/telegram_client.py connect` — первый раз потребуется код из Telegram

## Команды

| Команда | Описание |
|---------|----------|
| `connect` | Подключиться и авторизоваться |
| `list-chats` | Список всех чатов |
| `read-chat <id> [limit]` | Читать сообщения из чата |
| `send-message <id> <text>` | Отправить сообщение |

## Безопасность

- `.env`, `*.session`, `.string_session` — НЕ коммитить в репозиторий
- Отозвать доступ: my.telegram.org → Active sessions → terminate

## Ограничения

- Секретные чаты не поддерживаются
- Только собственные чаты и чаты где состоишь
