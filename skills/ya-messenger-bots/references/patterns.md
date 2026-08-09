# Code Patterns

## Polling Echo Bot (Python)

```python
import requests
import time

TOKEN = "your_oauth_token"
BASE = "https://bp.mssngr.yandex.net/public"
HEADERS = {"Authorization": f"OAuthTeam {TOKEN}"}

offset = 0
while True:
    resp = requests.get(
        f"{BASE}/bot/v1/messages/getUpdates",
        headers=HEADERS,
        params={"offset": offset, "limit": 100},
    )
    data = resp.json()
    for update in data.get("updates", []):
        offset = update["update_id"] + 1
        text = update.get("text")
        if text and not update["from"].get("robot"):
            chat_id = update["chat"]["id"]
            requests.post(
                f"{BASE}/bot/v1/messages/sendText",
                headers=HEADERS,
                json={"chat_id": chat_id, "text": f"You wrote: {text}"},
            )
    time.sleep(1)
```

---

## Webhook Bot (Python/Flask)

```python
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
TOKEN = "your_oauth_token"
BASE = "https://bp.mssngr.yandex.net/public"
HEADERS = {"Authorization": f"OAuthTeam {TOKEN}"}

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.json
    # TODO: verify TVM ticket from X-Ya-Service-Ticket
    text = update.get("text")
    if text and not update["from"].get("robot"):
        chat_id = update["chat"]["id"]
        requests.post(
            f"{BASE}/bot/v1/messages/sendText",
            headers=HEADERS,
            json={"chat_id": chat_id, "text": f"Received: {text}"},
        )
    return jsonify({"ok": True})
```

---

## Inline Keyboard with callback_data

```python
# Send a message with buttons
requests.post(f"{BASE}/bot/v1/messages/sendText", headers=HEADERS, json={
    "chat_id": chat_id,
    "text": "Choose an action:",
    "inline_keyboard": [
        {"text": "Confirm", "callback_data": {"action": "confirm"}},
        {"text": "Cancel", "callback_data": {"action": "cancel"}},
        {"text": "Documentation", "url": "https://docs.example.com"},
    ],
})

# Handle button press
callback = update.get("callback_data")
if callback:
    action = callback.get("action")
    if action == "confirm":
        requests.post(f"{BASE}/bot/v1/messages/sendText", headers=HEADERS, json={
            "chat_id": update["chat"]["id"],
            "text": "Confirmed!",
        })
    elif action == "cancel":
        requests.post(f"{BASE}/bot/v1/messages/sendText", headers=HEADERS, json={
            "chat_id": update["chat"]["id"],
            "text": "Cancelled.",
        })
```

---

## Action Buttons with server_action (Like/Dislike)

```python
# Send a message with rating buttons
requests.post(f"{BASE}/bot/v1/messages/sendText", headers=HEADERS, json={
    "chat_id": chat_id,
    "text": "Rate this response:",
    "action_buttons": {
        "buttons": [
            {
                "id": "like",
                "title": "Helpful",
                "icon": {"type": "messenger_icons", "value": "like"},
                "directives": [
                    {"type": "server_action", "name": "rate", "payload": {"v": 1}},
                ],
            },
            {
                "id": "dislike",
                "title": "Not helpful",
                "icon": {"type": "messenger_icons", "value": "dislike"},
                "directives": [
                    {"type": "server_action", "name": "rate", "payload": {"v": -1}},
                ],
            },
        ]
    },
})

# Handle server_action
bot_req = update.get("bot_request")
if bot_req:
    sa = bot_req["server_action"]
    if sa["name"] == "rate":
        rating = sa["payload"]["v"]
        # +1 = helpful, -1 = not helpful
```

---

## Suggest Buttons with send_message

```python
requests.post(f"{BASE}/bot/v1/messages/sendText", headers=HEADERS, json={
    "chat_id": chat_id,
    "text": "How can I help?",
    "suggest_buttons": {
        "layout": "false",
        "persist": False,
        "buttons": [
            {
                "id": "help",
                "title": "Help",
                "directives": [{"type": "send_message", "text": "/help"}],
            },
            {
                "id": "status",
                "title": "Status",
                "directives": [{"type": "send_message", "text": "/status"}],
            },
            {
                "id": "settings",
                "title": "Settings",
                "directives": [
                    {"type": "server_action", "name": "open_settings", "payload": {}},
                ],
            },
        ],
    },
})
```

---

## Sending Files

```python
# Multipart/form-data — new file
with open("report.pdf", "rb") as f:
    requests.post(
        f"{BASE}/bot/v1/messages/sendFile",
        headers={"Authorization": f"OAuthTeam {TOKEN}"},
        data={"chat_id": chat_id},
        files={"document": ("report.pdf", f, "application/pdf")},
    )

# Forward an existing file by file_id
requests.post(f"{BASE}/bot/v1/messages/shareFile", headers=HEADERS, json={
    "chat_id": chat_id,
    "file_id": "disk/5e05d58e-7e91-4c25-8ae0-c7e50d68290a",
})

# Send an image
with open("photo.jpg", "rb") as f:
    requests.post(
        f"{BASE}/bot/v1/messages/sendImage",
        headers={"Authorization": f"OAuthTeam {TOKEN}"},
        data={"chat_id": chat_id},
        files={"image": ("photo.jpg", f, "image/jpeg")},
    )
```

---

## Working with Threads

```python
# Reply in a thread (thread_id = message_id of the initial message)
requests.post(f"{BASE}/bot/v1/messages/sendText", headers=HEADERS, json={
    "chat_id": chat_id,
    "text": "Reply in thread",
    "thread_id": update["message_id"],
})
```

---

## Editing a Message

```python
# Send a message, save message_id
resp = requests.post(f"{BASE}/bot/v1/messages/sendText", headers=HEADERS, json={
    "chat_id": chat_id,
    "text": "Processing...",
})
msg_id = resp.json()["message_id"]

# Edit the message
requests.post(f"{BASE}/bot/v1/messages/sendText", headers=HEADERS, json={
    "chat_id": chat_id,
    "text": "Done! Result: ...",
    "message_id": msg_id,
})
```

---

## Ephemeral Message (Visible to One User Only)

```python
requests.post(f"{BASE}/bot/v1/messages/sendText", headers=HEADERS, json={
    "chat_id": chat_id,
    "text": "Only you can see this",
    "ephemeral": {
        "to_guid": update["from"]["id"],
        "trigger_id": update["meta"]["trigger_id"],
    },
})
```

---

## Creating a Chat

```python
resp = requests.post(f"{BASE}/bot/v1/chats/create", headers=HEADERS, json={
    "name": "Project Chat",
    "description": "Discussion for project X",
    "channel": False,
    "public": False,
    "members": [
        {"login": "user1@yandex-team.ru"},
        {"login": "user2@yandex-team.ru"},
    ],
    "admins": [
        {"login": "admin@yandex-team.ru"},
    ],
})
chat_id = resp.json()["chat_id"]
```

---

## Registering a Team Bot (Step by Step)

```python
import requests

# 1. Get the robot's OAuth token (do this once in a browser)
# https://oauth.yandex-team.ru/authorize?response_type=token&client_id=f45aca80c81144dd95dc150319c327a3

TOKEN = "robot_oauth_token"
TEAM_API = "https://bp.mssngr.yandex.net/team"
HEADERS = {"Authorization": f"OAuthTeam {TOKEN}"}

# 2. Register the bot
resp = requests.get(f"{TEAM_API}/register", headers=HEADERS)
print(resp.json())

# 3. Set up webhook
resp = requests.post(f"{TEAM_API}/update", headers=HEADERS, json={
    "webhook_url": "https://your-bot.example.com/webhook",
    "webhook_tvm_id": 2000473,
    "settings": {
        "get_typing": False,
        "send_message_first": True,
    },
})
print(resp.json())
```

---

## Handling Different Update Types

```python
def handle_update(update):
    # Text message
    if "text" in update and not update["from"].get("robot"):
        handle_text(update)

    # Inline button press
    elif "callback_data" in update:
        handle_callback(update)

    # server_action from suggest/action buttons
    elif "bot_request" in update:
        handle_bot_request(update)

    # File
    elif "file" in update:
        handle_file(update)

    # Images
    elif "images" in update:
        handle_images(update)

    # Membership change
    elif "chat_members_update" in update:
        handle_members_change(update)

    # Typing (informational, no retries)
    elif update.get("information_update_type") == "typing":
        pass  # usually ignored

    # Enhanced typing (with trigger_id for realtime suggest)
    elif "enhanced_typing" in update:
        handle_enhanced_typing(update)
```

---

## Poll

```python
# Create a poll
requests.post(f"{BASE}/bot/v1/messages/createPoll", headers=HEADERS, json={
    "chat_id": chat_id,
    "title": "When should we have the meeting?",
    "answers": ["Monday", "Wednesday", "Friday"],
    "is_anonymous": False,
    "max_choices": 1,
})

# Get results
resp = requests.get(f"{BASE}/bot/v1/polls/getResults", headers=HEADERS, params={
    "chat_id": chat_id,
    "message_id": poll_message_id,
})
```
