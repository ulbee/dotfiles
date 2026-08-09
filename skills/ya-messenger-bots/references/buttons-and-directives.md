# Buttons and Interactive Elements

## Inline Buttons (max 100)

Passed in `inline_keyboard` when sending a message. Array of objects.

```json
"inline_keyboard": [
  {"text": "Open", "url": "https://example.com"},
  {"text": "Confirm", "callback_data": {"action": "confirm", "id": 123}},
  {"text": "Action", "callback_data": {"action": "do_something"}}
]
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | yes | Button label |
| `callback_data` | object | no | JSON data, arrives in `update.callback_data` |
| `url` | string | no | URL to open |

`callback_data` and `url` are mutually exclusive. `callback_data` is an **object**, not a string.

---

## Suggest Buttons (max 100)

Suggestion buttons shown below the input field. Passed in `suggest_buttons`.

### Standard List

```json
"suggest_buttons": {
  "layout": "false",
  "persist": false,
  "buttons": [
    {
      "id": "btn1",
      "title": "Option 1",
      "directives": [
        {"type": "send_message", "text": "Selected option 1"}
      ]
    },
    {
      "id": "btn2",
      "title": "Option 2",
      "directives": [
        {"type": "server_action", "name": "select", "payload": {"v": 2}}
      ]
    }
  ]
}
```

### 2D Layout (button rows)

```json
"suggest_buttons": {
  "layout": "true",
  "persist": false,
  "buttons": [
    [
      {"id": "a1", "title": "Button 1"},
      {"id": "a2", "title": "Button 2"}
    ],
    [
      {"id": "b1", "title": "Button 3"}
    ]
  ]
}
```

### Suggest Button Fields

| Field | Type | Limit | Description |
|-------|------|-------|-------------|
| `id` | string | max 255 | Unique identifier |
| `title` | string | max 255 | Button text |
| `directives` | array | max 3 | Actions on press |

`persist: true` — buttons remain visible after being pressed.

---

## Action Buttons (max 6)

Reaction-style buttons (like/dislike). Passed in `action_buttons`.

```json
"action_buttons": {
  "buttons": [
    {
      "id": "like",
      "title": "Helpful",
      "icon": {"type": "messenger_icons", "value": "like"},
      "directives": [
        {"type": "server_action", "name": "rate", "payload": {"v": 1}}
      ]
    },
    {
      "id": "dislike",
      "title": "Not helpful",
      "icon": {"type": "messenger_icons", "value": "dislike"},
      "directives": [
        {"type": "server_action", "name": "rate", "payload": {"v": -1}}
      ]
    }
  ]
}
```

### Action Button Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Identifier (max 255) |
| `title` | string | yes | Button text (max 255) |
| `icon` | object | yes | Icon |
| `directives` | array | yes | Actions (max 3) |

### Icons

```json
{"type": "messenger_icons", "value": "like"}
```

Available `value` options: `like`, `pressed_like`, `dislike`, `pressed_dislike`.

---

## Directives (Button Actions)

Used in `directives` of suggest and action buttons. Each button can have up to 3 directives.

### `open_uri` — Open a URL

```json
{"type": "open_uri", "uri": "https://example.com/page"}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | `"open_uri"` |
| `uri` | string | yes | URL to open |

### `send_message` — Send a message from the user

```json
{
  "type": "send_message",
  "text": "Selected option A",
  "payload": {"option": "A"}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | `"send_message"` |
| `text` | string | yes | Text (max 6000) |
| `payload` | object | no | Arbitrary data |

### `server_action` — Send a request to the bot

```json
{
  "type": "server_action",
  "name": "rate_message",
  "payload": {"message_id": 123, "rating": 5}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | `"server_action"` |
| `name` | string | yes | Action name |
| `payload` | object | yes | Arbitrary data |

Delivered to the bot in `update.bot_request.server_action` with `name` and `payload`.

### `set_elements_state` — Change element state

```json
{
  "type": "set_elements_state",
  "ids": ["btn1", "btn2"],
  "state": "disabled",
  "timeout_seconds": 30
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | `"set_elements_state"` |
| `ids` | array[string] | yes | Element IDs to modify |
| `state` | string | yes | `"disabled"` or `"loading"` |
| `timeout_seconds` | int | no | 1–60, default 15 |

Used to disable buttons after a press or show a loading indicator.

---

## Realtime Suggest

Dynamic suggestions, 1–10 buttons. Sent via `POST /bot/v1/messages/sendRealtimeSuggest`.

```json
{
  "chat_id": "0/0/<uuid>",
  "user_id": "<uuid>",
  "trigger_id": "<encoded>",
  "suggest": {
    "buttons": [
      {
        "send_message_directive": {
          "type": "send_message",
          "text": "Suggestion 1"
        }
      },
      {
        "send_message_directive": {
          "type": "send_message",
          "text": "Suggestion 2"
        }
      }
    ]
  },
  "thread_id": 1647523230504005
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `chat_id`/`user_id`/`login` | one of | Recipient |
| `trigger_id` | yes | From `update.meta.trigger_id` or `enhanced_typing.trigger_id` |
| `suggest.buttons` | yes | 1–10 buttons with `send_message_directive` |
| `thread_id` | no | Thread ID |
