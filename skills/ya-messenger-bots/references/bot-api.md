# Bot API — Full Endpoint Reference

## Receiving Updates

### `GET/POST /bot/v1/messages/getUpdates` — long polling

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `offset` | int | 0 | ID of the next update |
| `limit` | int | 100 | Number of updates (100–1000) |

Returns `{"ok": true, "updates": [...]}`. Use `offset = last_update_id + 1`.

---

## Sending Messages

### `POST /bot/v1/messages/sendText`

Recipient — one of: `chat_id`, `user_id`, `login`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `chat_id` | string | one of three | Chat ID (`0/0/<uuid>`) |
| `user_id` | string | one of three | User UUID |
| `login` | string | one of three | User login |
| `text` | string | yes* | Message text (max 6000) |
| `card` | object | yes* | DivKit card (*either text or card required) |
| `inline_keyboard` | array | no | Inline buttons (max 100) |
| `suggest_buttons` | object | no | Suggest buttons (max 100) |
| `action_buttons` | object | no | Action buttons (max 6) |
| `reply_message_id` | int | no | Message ID to reply to |
| `thread_id` | int | no | Thread ID (timestamp of the initial message) |
| `message_id` | int | no | For editing an existing message |
| `disable_notification` | bool | false | Send without notification |
| `important` | bool | false | Mark as important |
| `disable_web_page_preview` | bool | false | Disable link preview |
| `payload_id` | string | no | Deduplication ID |
| `custom_from` | object | no | Custom sender (requires `allow_custom_from`) |
| `ephemeral` | object | no | Ephemeral message |
| `workspace_notification_settings` | object | no | Workspace settings |

**Response:**
```json
{
  "ok": true,
  "message_id": 1647523230504005,
  "chat": {"type": "group", "id": "0/0/<uuid>", "title": "..."},
  "meta": {"client_workspace": "...", "trigger_id": "..."}
}
```

### `POST /bot/v1/messages/sendFile`
Multipart/form-data. Fields: `chat_id`/`user_id`/`login` + file in `document` field.

### `POST /bot/v1/messages/shareFile`
JSON. Fields: `chat_id` + `file_id` (format `disk/<uuid>`).

### `GET /bot/v1/messages/getFile`
Parameter: `file_id`. Returns file content.

### `POST /bot/v1/messages/sendImage`
Multipart/form-data. Similar to sendFile, file in `image` field.

### `POST /bot/v1/messages/shareImage`
JSON. Fields: `chat_id` + `file_id`.

### `POST /bot/v1/messages/sendGallery`
Multipart/form-data. 1–10 images. Optional `text`.

### `POST /bot/v1/messages/shareGallery`
JSON. Array of `file_ids` + `chat_id`.

### `POST /bot/v1/messages/sendSticker`
JSON: `chat_id`, `sticker_id`, `sticker_set_id`.

### `POST /bot/v1/messages/sendSystemMessage`
System message. JSON: `chat_id`, `text`.

### `POST /bot/v1/messages/sendNotification`
Notification for specific users. JSON: `chat_id`, `text`, `to_users`.

### `POST /bot/v1/messages/sendTyping`
JSON: `chat_id`. Shows "bot is typing" indicator.

### `POST /bot/v1/messages/delete`
JSON: `chat_id`, `message_id`.

---

## Polls

### `POST /bot/v1/messages/createPoll`
JSON: `chat_id`, `title`, `answers` (2–100), `is_anonymous`, `max_choices`.

### `GET /bot/v1/polls/getResults`
Parameters: `chat_id`, `message_id`.

### `GET /bot/v1/polls/getVoters`
Parameters: `chat_id`, `message_id`, `answer_index`.

---

## Realtime Suggest

### `POST /bot/v1/messages/sendRealtimeSuggest`

```json
{
  "chat_id": "0/0/<uuid>",
  "user_id": "<uuid>",
  "trigger_id": "<encoded>",
  "suggest": {
    "buttons": [
      {"send_message_directive": {"type": "send_message", "text": "Suggestion 1"}},
      {"send_message_directive": {"type": "send_message", "text": "Suggestion 2"}}
    ]
  },
  "thread_id": 1647523230504005
}
```

1–10 buttons. `trigger_id` is required (from `update.meta.trigger_id` or `update.enhanced_typing.trigger_id`).

---

## Bot Request

### `POST /bot/v1/messages/sendBotRequest`
Handles server_action from buttons. Response to `update.bot_request`.

---

## Bot Management

### `GET /bot/v1/self/get`
Returns bot info: `uid`, `guid`, `nickname`, `display_name`, `webhook_url`, `settings`.

### `POST /bot/v1/self/update`
JSON: `webhook_url`, `settings` (object with flags).

```json
{
  "webhook_url": "https://your-bot.example.com/webhook",
  "settings": {
    "get_typing": true,
    "send_message_first": true
  }
}
```

To reset webhook: `{"webhook_url": null}`.

---

## Chats

### `GET /bot/v1/chats/get`
Parameter: `chat_id`. Returns: `type`, `id`, `title`, `description`, `members_count`.

### `POST /bot/v1/chats/create`

```json
{
  "name": "Chat name",
  "description": "Description",
  "channel": false,
  "public": true,
  "avatar_url": "https://example.com/avatar.png",
  "admins": [{"login": "admin@"}, {"id": "<uuid>"}],
  "members": [{"login": "user@"}],
  "subscribers": [{"login": "sub@"}],
  "organization_id": 12345
}
```

| Field | Limit |
|-------|-------|
| `name` | max 200 characters |
| `description` | max 500 characters |
| `admins` | max 100 |
| `members` | max 500 (for chats) |
| `subscribers` | max 500 (for channels) |

**Response:** `{"ok": true, "chat_id": "0/0/<uuid>", "invite_hash": "<uuid>"}`

### `POST /bot/v1/chats/updateMembers`
JSON: `chat_id`, `add` and/or `remove` (arrays of UserId). Max 500 per request.

---

## Users

### `GET /bot/v1/users/getUserLink`
Parameter: `user_id` or `login`. Returns profile link.

### `POST /bot/v1/users/miniapps`
Set mini-app URL for users. Max 50 per request.

### `GET /bot/v1/users/miniapps`
Get current mini-app settings.

---

## Meta API — Endpoints

Authorization: TVM service ticket in `X-Ya-Service-Ticket`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/bots` | Create a common bot |
| GET | `/api/bots/{uid}` | Get bot data |
| POST | `/api/bots/{uid}/update` | Update bot |
| POST | `/api/bots/{uid}/token` | Generate OAuth token |
| POST | `/api/bots/check-nickname` | Check nickname availability |
| POST | `/api/bots/{uid}/avatar` | Set avatar |
| POST | `/api/bots/{uid}/online_status` | Heartbeat / online status |

**Creating a bot:**
```json
{
  "nickname": "my-bot",
  "display_name": "My Bot",
  "org_id": 0,
  "type": "botplatform_internal",
  "webhook_url": "https://example.com/webhook",
  "webhook_tvm_id": 200000,
  "settings": {
    "get_typing": false,
    "send_message_first": false
  },
  "localization": {
    "en": {"display_name": "My Bot", "avatar_id": "mssngr/12345/en"}
  },
  "localization_descriptor": {"default": "ru"}
}
```

Required: `nickname` (max 50), `display_name`, `org_id`.

---

## Team API — Endpoints

Authorization: `Authorization: OAuthTeam <token>`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/team/register` | Register a team bot (nickname `robot-*`) |
| GET | `/team/me` | Current bot info |
| POST | `/team/update` | Update settings |
| POST | `/team/online_status` | Enable/disable heartbeat |

---

## Update Format

```json
{
  "update_id": 1571239,
  "message_id": 1702323240544005,
  "timestamp": 1702323240,
  "from": {
    "login": "user@example.com",
    "id": "447c35f4-...",
    "display_name": "User Name",
    "robot": false
  },
  "chat": {
    "type": "group",
    "id": "0/0/4f24b544-...",
    "title": "Support Chat",
    "description": "...",
    "thread_id": 1647523230504005,
    "to_users": ["user_id_1"]
  },
  "text": "Hello!",
  "callback_data": {"action": "confirm", "id": 123},
  "file": {"id": "disk/<uuid>", "name": "report.pdf", "size": 2048},
  "images": [[{"file_id": "disk/<uuid>?size=small", "width": 150, "height": 100, "size": 20480, "name": "photo.jpg"}]],
  "sticker": {"id": "sticker456", "set_id": "stickerset123"},
  "poll": {"title": "Question?", "answers": ["Yes", "No"], "is_anonymous": false, "max_choices": 1},
  "voice": {"file": {"id": "disk/<uuid>", "name": "voice.ogg", "size": 12345}, "duration": 15, "was_recognized": true, "recognition_disabled": false},
  "forwarded_messages": [],
  "reply_to_message": {"update_id": 1571238, "message_id": 1702323240544000},
  "mentioned_users": [{"login": "user@", "id": "<uuid>", "display_name": "User", "robot": false}],
  "chat_members_update": {
    "new": [{"login": "new@", "display_name": "New User"}],
    "removed": [{"login": "old@", "display_name": "Old User"}]
  },
  "bot_request": {
    "server_action": {"name": "rate", "payload": {"rating": 5}},
    "element_id": "btn_rate",
    "errors": [],
    "custom_payload": {}
  },
  "enhanced_typing": {
    "trigger_id": "trigger123",
    "meta": {"locale": "ru_RU", "context": "chat_message"}
  },
  "information_update_type": "typing",
  "important": false,
  "meta": {
    "client_workspace": "workspace1",
    "client_supported_features": 12345,
    "trigger_id": "trigger_abc",
    "referer_service_info": {"service": "web_client"}
  }
}
```

### Update Types

| Field | Event type |
|-------|------------|
| `text` | Text message |
| `callback_data` | Inline button press (JSON object) |
| `bot_request` | server_action from suggest/action buttons |
| `file` | File |
| `images` | Images |
| `sticker` | Sticker |
| `poll` | Poll |
| `voice` | Voice message |
| `chat_members_update` | Chat membership change |
| `information_update_type: "typing"` | User is typing |
| `enhanced_typing` | Extended typing with trigger_id |
| `forwarded_messages` | Forwarded messages |

### Helper Structures

**UserId** — one of:
- `{"login": "user@example.com"}`
- `{"id": "6d8d04f7-..."}`

**custom_from:**
```json
{
  "guid": "<uuid>",
  "robot": false,
  "display_name": "John Doe",
  "avatar_id": "avatar123",
  "localization": {"ru": {"display_name": "Ivan", "avatar_id": "mssngr/12345/ru"}}
}
```

**ephemeral:**
```json
{
  "to_guid": "<uuid>",
  "trigger_id": "<encoded>",
  "payload_id": "payload123",
  "version": 1
}
```

### Error Format

```json
{"ok": false, "description": "Detailed error message", "code": "error_code"}
```

Common codes: `unsupported_directive`, `invalid_directive_payload`, `client_error`, `user_not_found`.
