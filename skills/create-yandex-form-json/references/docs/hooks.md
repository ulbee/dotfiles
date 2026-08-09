# Интеграции (Hooks)

Интеграции выполняются после отправки формы. Они группируются в **hooks** — каждая группа содержит одну или несколько **subscriptions** и может иметь собственные условия срабатывания.

## Структура

```json
"hooks": [
  {
    "name": "Название группы",
    "active": true,
    "conditions": [],
    "subscriptions": [ /* интеграции */ ]
  }
]
```

| Поле | Тип | По умолчанию | Описание |
|------|-----|---------|----------|
| `name` | string \| null | "Новая группа интеграций" | Название для навигации в UI |
| `active` | bool | `true` | Неактивные сохраняются, но не выполняются |
| `conditions` | array | `[]` | Условия срабатывания группы (стандартный формат Condition) |
| `subscriptions` | array | — | Список интеграций |

## Типы интеграций (Subscription)

Общие поля для всех типов:

| Поле | Тип | По умолчанию | Описание |
|------|-----|---------|----------|
| `type` | string | — | **Обязательно.** Тип интеграции |
| `active` | bool | `true` | Включена ли интеграция |
| `follow` | bool | `false` | Отслеживать ошибки (уведомлять наблюдателей) |
| `language` | string | `"from_request"` | Язык рендеринга шаблонов |
| `variables` | array | `[]` | Переменные для подстановки в шаблоны |

---

### `"email"` — Отправка письма

```json
{
  "type": "email",
  "active": true,
  "email_to_address": "hr@company.com",
  "email_from_address": "forms@company.com",
  "email_from_title": "HR-форма",
  "subject": "Новая заявка от {var_name}",
  "body": "<p>Получена заявка.</p><p>Имя: {var_name}</p>",
  "email_spam_check": false,
  "headers": [
    { "name": "Reply-To", "value": "{var_email}" }
  ],
  "attachments": {
    "question": { "all": false, "items": ["q5_resume"] },
    "template": []
  },
  "variables": [ /* ... */ ]
}
```

| Поле | Описание |
|------|----------|
| `email_to_address` | Получатель(и), через запятую. Поддерживает переменные |
| `email_from_address` | Отправитель. На бизнес-сайтах игнорируется |
| `email_from_title` | Имя отправителя |
| `subject` | Тема письма. Поддерживает переменные |
| `body` | Тело письма (HTML). Поддерживает переменные |
| `email_spam_check` | Проверка на спам перед отправкой |
| `headers` | Доп. заголовки: только `Reply-To` или начинающиеся с `X-` |
| `attachments` | Вложения: из вопросов (`question`), статические (`static`), по шаблону (`template`) |

---

### `"tracker"` — Создание тикета в Яндекс.Трекере

```json
{
  "type": "tracker",
  "active": true,
  "queue": "SUPPORT",
  "subject": "Обращение: {var_topic}",
  "body": "Описание: {var_description}",
  "issue_type": 2,
  "priority": 2,
  "assignee": "robot-forms",
  "author": "{var_login}",
  "fields": [
    {
      "key": { "slug": "tags", "type": "string" },
      "value": "from-form",
      "only_with_value": true
    }
  ],
  "variables": [ /* ... */ ]
}
```

| Поле | Описание |
|------|----------|
| `queue` | Очередь трекера (напр. `"SUPPORT"`). Обязательно если нет `parent` |
| `parent` | Ключ родительского тикета (напр. `"SUPPORT-123"`). Обязательно если нет `queue` |
| `subject` | Заголовок тикета |
| `body` | Описание тикета |
| `issue_type` | Числовой ID типа тикета. Обязательно |
| `priority` | Числовой ID приоритета. Обязательно |
| `assignee` | Логин исполнителя. Поддерживает переменные |
| `author` | Логин автора. Поддерживает переменные |
| `fields` | Дополнительные поля тикета (массив `{key, value, only_with_value}`) |

---

### `"wiki"` — Запись на Wiki-страницу или в Wiki-таблицу

**Текст на страницу:**
```json
{
  "type": "wiki",
  "active": true,
  "supertag": "teams/hr/applications",
  "body": "== Заявка ==\n{var_content}",
  "insert_to_begin": false,
  "variables": [ /* ... */ ]
}
```

**Запись в Wiki-грид (таблицу):**
```json
{
  "type": "wiki",
  "active": true,
  "supertag": "teams/hr/applications",
  "grid_data": {
    "grid_id": "123",
    "title": "Заявки",
    "cols": [
      { "key": { "slug": "name", "type": "string" }, "value": "{var_name}" },
      { "key": { "slug": "date", "type": "string" }, "value": "{var_date}" }
    ]
  },
  "variables": [ /* ... */ ]
}
```

| Поле | Описание |
|------|----------|
| `supertag` | Путь wiki-страницы. Может быть URL (путь извлекается) |
| `body` | Текст для добавления на страницу. Поддерживает переменные |
| `grid_data` | Описание таблицы (`grid_id`, `title`, `cols[]`). Альтернатива `body` |
| `insert_to_begin` | `true` — вставить в начало; `false` (по умолчанию) — в конец |

---

### `"jsonrpc"` — JSON-RPC вызов

```json
{
  "type": "jsonrpc",
  "active": true,
  "url": "https://api.example.com/rpc",
  "method": "createUser",
  "tvm_client": "12345",
  "params": [
    { "name": "email", "value": "{var_email}", "only_with_value": true },
    { "name": "name", "value": "{var_name}" }
  ],
  "variables": [ /* ... */ ]
}
```

---

### `"post"` / `"put"` — HTTP POST/PUT с данными формы

```json
{
  "type": "post",
  "active": true,
  "url": "https://api.example.com/webhook",
  "format": "json",
  "tvm_client": null,
  "questions": { "all": true },
  "headers": [
    { "name": "X-Source", "value": "yandex-forms" }
  ],
  "variables": [ /* ... */ ]
}
```

| Поле | Описание |
|------|----------|
| `url` | URL для запроса. Поддерживает переменные |
| `format` | `"json"` (по умолчанию) или `"xml"` |
| `questions` | Какие вопросы включить: `{ "all": true }` или `{ "all": false, "items": ["q1_slug", "q2_slug"] }` |
| `tvm_client` | ID TVM-клиента для сервисной авторизации |
| `headers` | HTTP-заголовки |

---

### `"http"` — Произвольный HTTP-запрос

```json
{
  "type": "http",
  "active": true,
  "url": "https://api.example.com/endpoint",
  "method": "patch",
  "body": "{\"user\": \"{var_login}\", \"status\": \"approved\"}",
  "headers": [
    { "name": "Content-Type", "value": "application/json" },
    { "name": "Authorization", "value": "Bearer {var_token}" }
  ],
  "variables": [ /* ... */ ]
}
```

| Поле | Описание |
|------|----------|
| `method` | `"get"`, `"post"`, `"patch"`, `"put"`, `"delete"`. по умолчанию: `"post"` |
| `body` | Тело запроса. Поддерживает переменные |

---

### `"function"` — Облачная функция

```json
{
  "type": "function",
  "active": true,
  "function_id": "d4e5f6a7b8c9d0e1f2a3b4c5",
  "params": [
    { "name": "action", "value": "process_form" }
  ],
  "variables": [ /* ... */ ]
}
```

---

## Переменные (Variables)

Переменные подставляют данные формы в шаблоны интеграций через синтаксис `{variable_id}`.

```json
{
  "id": "aabbccddeeff00112233aabb",
  "type": "form.question_answer",
  "question": "q1_email"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | string | 24-символьный hex. При импорте перемаппливается; ссылки `{old_id}` в текстах заменяются на `{new_id}` |
| `type` | string | Тип переменной (источник данных) |
| `question` | string \| null | Slug вопроса. Обязательно для типов `form.question_*` |
| `renderer` | string \| null | Формат рендеринга |
| `filters` | array | Фильтры обработки значения (последовательно) |
| `name` | string \| null | Имя для спецтипов (`request.header`, `request.cookie`, `yav.secret`) |
| `secret` / `version` | string \| null | Для `yav.secret` |

### Типы переменных

| Тип | Источник |
|------|----------|
| `form.question_answer` | Ответ на конкретный вопрос |
| `form.name` | Название формы |
| `form.questions_json` | Все ответы в JSON |
| `request.header` | HTTP-заголовок запроса |
| `request.query_param` | GET-параметр |
| `request.cookie` | Cookie |
| `yav.secret` | Секрет из YAV |

## Вложения (Attachments)

Для `email` и `tracker` интеграций:

```json
"attachments": {
  "question": {
    "all": false,
    "items": ["q5_upload_file"]
  },
  "static": [
    { "name": "instructions.pdf", "links": { "orig": "https://..." } }
  ],
  "template": [
    {
      "id": 1,
      "name": "Заявка",
      "type": "pdf",
      "body": "Имя: {var_name}\nДата: {var_date}",
      "variables": [ /* ... */ ]
    }
  ]
}
```

| Источник | Описание |
|----------|----------|
| `question` | Файлы из file-вопросов: `all: true` или конкретные slugs |
| `static` | Статические файлы по ссылке |
| `template` | Генерируемые файлы (PDF или TXT) по шаблону с переменными |
