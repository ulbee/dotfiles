---
name: ya-messenger-bots
description: >
  Developing bots for Yandex Messenger. Use when working with Bot API,
  Meta API, or Team API of Yandex Messenger. Triggers: "yandex messenger",
  "messenger bot", "bot platform", "bp.mssngr", "sendText", "getUpdates",
  "inline keyboard messenger", "webhook messenger", "create bot messenger",
  "send message messenger", "callback_data", "server_action",
  "suggest buttons", "sendGallery", "createPoll", "OAuthTeam messenger",
  "TVM messenger", "яндекс мессенджер", "бот-платформа", "создать бота",
  "отправить сообщение в мессенджер", "вебхук мессенджер".
user-invocable: false
---

# Yandex Messenger Bots

Reference for building bots on the Yandex Messenger platform.

**When to use:** writing bot code, integrating with Messenger, registering bots, handling messages, building inline keyboards.

**When NOT to use:** Telegram bots (use `telegram-user-client` skill), other platforms.

---

## Three APIs and Base URLs

| API | Purpose | Testing | Production |
|-----|---------|---------|------------|
| **Bot API** | Send/receive messages | `https://test.bp.mssngr.yandex.net/public` | `https://bp.mssngr.yandex.net/public` |
| **Meta API** | Manage common bots | `https://botplatform-internal.test.yandex.net/api` | `https://botplatform-internal.yandex.net/api` |
| **Team API** | Manage team bots | `https://test.bp.mssngr.yandex.net/team` | `https://bp.mssngr.yandex.net/team` |

Prestable (alpha): replace `test` → `alpha`. TVM ID: Testing — 2000472, Prestable — 2001666, Production — 2000473.

---

## Authentication

| API | Method | Header |
|-----|--------|--------|
| Bot API (team) | OAuth | `Authorization: OAuthTeam <token>` |
| Bot API (common) | OAuth | `Authorization: OAuth <token>` |
| Meta API | TVM | `X-Ya-Service-Ticket` |
| Team API | OAuth | `Authorization: OAuthTeam <token>` |
| Team API (webhook setup) | OAuth + TVM | Both headers |
| Webhook verification | TVM | `X-Ya-Service-Ticket` |

**Getting a team bot token:** https://oauth.yandex-team.ru/authorize?response_type=token&client_id=f45aca80c81144dd95dc150319c327a3

**Getting a common bot token:** `POST /api/bots/{uid}/token` via Meta API.

---

## Scenarios

### Create a polling bot
1. Obtain an OAuth token for the bot
2. Loop `GET /bot/v1/messages/getUpdates` with `offset` and `limit`
3. Process `updates[]`, reply via `POST /bot/v1/messages/sendText`
4. Use `offset = last_update_id + 1` for pagination

For a working Python echo bot example, read `references/patterns.md`.

### Create a webhook bot
1. Implement an HTTP endpoint that accepts POST requests
2. Register the webhook: `POST /bot/v1/self/update` with `webhook_url`
3. Verify the TVM ticket from `X-Ya-Service-Ticket` on incoming requests
4. Open network access via Puncher
5. Bot must be idempotent — webhook delivers at-least-once

Polling and webhook are mutually exclusive — setting `webhook_url` disables `getUpdates`.

For a Flask skeleton, read `references/patterns.md`.

### Send a message with buttons
1. `POST /bot/v1/messages/sendText` with `inline_keyboard`, `suggest_buttons`, or `action_buttons`
2. Inline buttons: `callback_data` (JSON object) or `url`
3. Suggest buttons: shown below the input field, with directives (`send_message`, `server_action`)
4. Action buttons: like/dislike with icons

For JSON structures of all button types and directives, read `references/buttons-and-directives.md`.

### Handle a button press
1. `callback_data` arrives in `update.callback_data` as a JSON object (not a string!)
2. `server_action` arrives in `update.bot_request.server_action` with `name` and `payload`
3. For realtime suggest: `POST /bot/v1/messages/sendRealtimeSuggest` with `trigger_id` from the update

For handling examples, read `references/patterns.md`.

### Register a team bot
1. Create a robot account on Staff (nickname must start with `robot-`): https://wiki.yandex-team.ru/diy/zombik/
2. Obtain an OAuth token for the robot
3. `GET {TEAM_API}/team/register` with `Authorization: OAuthTeam <token>`
4. `POST {TEAM_API}/team/update` with `webhook_url` and `webhook_tvm_id`
5. Request network access via Puncher

### Register a common bot
1. Set up TVM access to the Meta API
2. `POST /api/bots` with `nickname`, `display_name`, `org_id`
3. `POST /api/bots/{uid}/token` — generate an OAuth token
4. Use the token for the Bot API

### Send a file/image
1. `POST /bot/v1/messages/sendFile` — multipart/form-data
2. `POST /bot/v1/messages/shareFile` — forward by `file_id`
3. `POST /bot/v1/messages/sendImage` / `shareImage` — same for images
4. `POST /bot/v1/messages/sendGallery` — gallery of 1–10 images

For a multipart example, read `references/patterns.md`.

### Manage chats
1. `POST /bot/v1/chats/create` — create a chat/channel (name max 200, members max 500)
2. `POST /bot/v1/chats/updateMembers` — add/remove members (max 500 per request)
3. `GET /bot/v1/chats/get` — get chat info

---

## Bot Settings

Set via `POST /bot/v1/self/update`. All default to `false`.

| Setting | Description |
|---------|-------------|
| `get_typing` | Receive "user is typing" events |
| `get_seen_markers` | Receive "message read" events |
| `get_members_changed` | Receive chat membership change events |
| `manual_seen_marker` | Send read markers manually |
| `auto_load_public_url` | Automatically get public file URLs |
| `send_message_first` | Allow bot to initiate private chats |
| `allow_custom_from` | Allow sending with a custom name/avatar |

---

## Webhooks

| Update type | Guarantee | Retries |
|-------------|-----------|---------|
| Informational (typing, seen) | at most once | no |
| Messages | at least once | yes, up to 24 hours |

**Order:** guaranteed per (bot + chat) pair.

**Retries** (on connection timeout 100ms / read timeout 1s / HTTP 5xx):
- Attempts 1–8: `send_time + attempt × 5` sec
- Attempts 9+: `send_time + attempt × 45` sec
- HTTP 2xx/4xx — final response (no retries)
- P99 latency: 500ms. Max RPS: 600 / webhook_response_time_ms

**Security:** TVM ticket required, network access via Puncher.

---

## Limits

| Resource | Limit |
|----------|-------|
| Message text | 6000 characters |
| Inline buttons | 100 |
| Suggest buttons | 100 |
| Action buttons | 6 |
| Realtime suggest | 1–10 |
| Poll answers | 2–100 |
| Gallery | 1–10 images |
| Members (update/create) | 500 |
| Admins (create) | 100 |
| Chat name | 200 characters |
| Chat description | 500 characters |
| Bot nickname | 50 characters |
| Polling limit | 100–1000 |

---

## Gotchas

1. **Polling and webhook are mutually exclusive** — setting `webhook_url` disables `getUpdates`
2. **`callback_data` is an object**, not a string
3. **Webhook requires TVM** — OAuth alone is not enough for verification
4. **`send_message_first`** must be enabled for the bot to initiate private chats
5. **`allow_custom_from`** must be enabled for custom sender name/avatar
6. **100 inline buttons is the total limit**, not per row
7. **Bot must be idempotent** — at-least-once delivery means duplicates are possible
8. **In group chats** the bot only receives messages with a mention or reply
9. **`message_id` is timestamp-based** — not unique across bots
10. **`trigger_id`** — Base64 string required for `sendRealtimeSuggest` and ephemeral messages
11. **Team bot nickname must start with `robot-`**

---

## OpenAPI Specs in Arcadia

- **Bot API:** `~/arcadia/yandex360/backend/mssngr/ya360-mssngr-bot-client-service/openapi/api/public-bot-api.yaml`
- **Meta API:** `~/arcadia/yandex360/backend/mssngr/ya360-mssngr-bot-management/openapi/api/meta-api.yaml`
- **Team API:** `~/arcadia/yandex360/backend/mssngr/ya360-mssngr-bot-management/openapi/api/team-api.yaml`

## References

- Full endpoint reference and Update format: [references/bot-api.md](references/bot-api.md)
- Button and directive JSON structures: [references/buttons-and-directives.md](references/buttons-and-directives.md)
- Python code examples: [references/patterns.md](references/patterns.md)
