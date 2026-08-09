# Telegram User Client

Умеет читать чаты, отправлять сообщения и скачивать файлы от лица пользователя.

## Установка

```bash
# 1. Получи credentials на my.telegram.org
#    → API development tools → создай приложение
#    → Скопируй api_id и api_hash

# 2. Установи зависимости
cd deps
pip install telethon python-dotenv --target=.
cd ..

# 3. Заполни .env
cp .env.example .env
# вставь свои api_id, api_hash, phone

# 4. Получи string session
# Первый запуск → введи код из Telegram (OTP)
python3 telegram_client.py connect

# 5. Используй
python3 telegram_client.py list-chats
python3 telegram_client.py send-message <chat_id> "Привет!"
```

## Команды

| Команда | Описание |
|---------|----------|
| `connect` | Подключиться и авторизоваться |
| `list-chats` | Список всех чатов |
| `read-chat <id> [limit]` | Читать сообщения из чата |
| `send-message <id> <text>` | Отправить сообщение |

## Структура

```
SKILL.md            ← это
telegram_client.py  ← ядро
telegram_tool.py    ← обёртка для OpenClaw
.env.example        ← шаблон конфига (БЕЗ реальных данных!)
```

## Безопасность

Никогда не коммить `.env`, `*.session`, `.string_session` в репозиторий!
