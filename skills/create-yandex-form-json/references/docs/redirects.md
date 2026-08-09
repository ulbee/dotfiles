# Перенаправления (Redirects)

После отправки формы пользователь может быть перенаправлен на внешний URL или на другую форму. Поддерживаются условные редиректы — разные URL в зависимости от ответов.

## Структура

```json
"redirects": [
  {
    "enabled": true,
    "url": "https://example.com/thanks",
    "timeout": 5000,
    "with_delay": true,
    "auto_redirect": false,
    "button": "Перейти",
    "keep_iframe": true,
    "conditions": [],
    "params": {},
    "variables": []
  }
]
```

## Поля

| Поле | Тип | По умолчанию | Описание |
|------|-----|---------|----------|
| `enabled` | bool | `true` | Включён ли редирект |
| `url` | string \| null | — | URL для перенаправления. Поддерживает переменные |
| `next_survey` | int \| string \| null | — | ID другой формы. Альтернатива `url` |
| `timeout` | int | `5000` | Задержка перед перенаправлением (мс). Используется при `with_delay: true` |
| `with_delay` | bool | `true` | Показать страницу "спасибо" перед редиректом |
| `auto_redirect` | bool | `false` | Автоматический редирект после таймаута. На бизнес-сайтах всегда `false` |
| `button` | string \| null | "Перейти" | Текст кнопки. Читается из первого редиректа |
| `keep_iframe` | bool | `true` | При iframe: редирект внутри iframe (`true`) или в родительском окне (`false`) |
| `conditions` | array | `[]` | Условия срабатывания (стандартный формат Condition) |
| `params` | object | `{}` | GET-параметры для URL. Значения поддерживают переменные `{variable_id}` |
| `variables` | array | `[]` | Переменные для подстановки в `params` |

## Условный редирект

Разные URL в зависимости от ответов — через `conditions` на каждом элементе `redirects[]`:

```json
"redirects": [
  {
    "enabled": true,
    "url": "https://example.com/premium",
    "conditions": [
      {
        "items": [
          { "operator": "and", "type": "question", "condition": "eq", "question": "q1_plan", "value": "premium" }
        ]
      }
    ]
  },
  {
    "enabled": true,
    "url": "https://example.com/basic",
    "conditions": [
      {
        "items": [
          { "operator": "and", "type": "question", "condition": "eq", "question": "q1_plan", "value": "basic" }
        ]
      }
    ]
  },
  {
    "enabled": true,
    "url": "https://example.com/thanks",
    "conditions": []
  }
]
```

Редиректы проверяются по порядку — первый с выполненными условиями срабатывает. Последний без условий — fallback.

## Редирект на другую форму

```json
{
  "enabled": true,
  "next_survey": 12345,
  "with_delay": false
}
```

`next_survey` принимает int (ID формы) или string (hex ID).

## GET-параметры с переменными

Передать данные формы в URL через query-параметры:

```json
{
  "url": "https://crm.example.com/lead",
  "params": {
    "name": "{var_name}",
    "email": "{var_email}",
    "source": "yandex-form"
  },
  "variables": [
    { "id": "aabbccddeeff00112233aa01", "type": "form.question_answer", "question": "q1_name" },
    { "id": "aabbccddeeff00112233aa02", "type": "form.question_answer", "question": "q2_email" }
  ]
}
```

Результат: `https://crm.example.com/lead?name=Иван&email=ivan@mail.ru&source=yandex-form`

## Устаревшее поле `redirect`

Top-level `redirect` (единственное число) — deprecated. Если задан `redirects`, поле `redirect` игнорируется для настройки перенаправления, но из `redirect.button` читается текст кнопки. Используйте `redirects` для новых форм.
