# Тестовый режим (Quiz)

Превращает обычную форму в тест с подсчётом баллов и показом результатов.

## Включение на уровне вопроса

Добавьте `has_quiz: true` на вопрос типа `enum` и укажите `correct` / `scores` на каждом варианте ответа:

```json
{
  "type": "enum",
  "widget": "radio",
  "has_quiz": true,
  "items": [
    { "slug": "paris", "label": "Париж", "correct": true, "scores": 10 },
    { "slug": "london", "label": "Лондон", "correct": false, "scores": 0 },
    { "slug": "berlin", "label": "Берлин", "correct": false, "scores": 0 }
  ]
}
```

| Поле на Choice | Тип | Описание |
|----------------|-----|----------|
| `correct` | bool \| null | Является ли вариант правильным |
| `scores` | number \| null | Баллы за выбор (макс. 1 000 000) |

## Квиз для текстовых вопросов

Для `type: "string"` используйте `quiz_items` вместо `items`:

```json
{
  "type": "string",
  "has_quiz": true,
  "quiz_items": [
    { "label": "42", "correct": true, "scores": 5 },
    { "label": "сорок два", "correct": true, "scores": 5 }
  ]
}
```

Несколько вариантов правильного ответа — каждый со своим `label`.

## Настройка результатов (объект `quiz` верхнего уровня)

```json
"quiz": {
  "show_results": true,
  "show_correct": true,
  "calc_method": "range",
  "pass_scores": 7.0,
  "items": [
    { "title": "Отлично!", "description": "Вы эксперт в этой теме" },
    { "title": "Хорошо", "description": "Почти всё правильно" },
    { "title": "Стоит подучить", "description": "Попробуйте ещё раз" }
  ]
}
```

| Поле | Тип | По умолчанию | Описание |
|------|-----|---------|----------|
| `show_results` | bool | `false` | Показывать набранные баллы после отправки |
| `show_correct` | bool | `false` | Показывать правильные ответы |
| `calc_method` | `"range"` \| `"scores"` | `"range"` | `"range"` — результат по диапазонам из `items`; `"scores"` — просто число баллов |
| `pass_scores` | number | `0.0` | Порог прохождения теста |
| `items` | array | `[]` | Диапазоны результатов (заголовок + описание + опциональная картинка) |

### Элемент `items[]`

```json
{
  "title": "Результат",
  "description": "Развёрнутое описание",
  "image": { "name": "result.png", "links": { "orig": "https://..." } }
}
```

`title` обязателен (дефолт: "Результат"). `description` и `image` — опциональны.

## Полный пример: квиз с тремя вопросами

```json
{
  "version": 2,
  "name": "Тест по географии",
  "quiz": {
    "show_results": true,
    "show_correct": true,
    "calc_method": "range",
    "pass_scores": 20,
    "items": [
      { "title": "Превосходно!", "description": "Все ответы верны" },
      { "title": "Неплохо", "description": "Есть над чем поработать" }
    ]
  },
  "questions": {
    "pages": [
      {
        "items": [
          {
            "type": "enum",
            "widget": "radio",
            "label": "Столица Франции?",
            "slug": "q1_france_capital",
            "has_quiz": true,
            "items": [
              { "slug": "paris", "label": "Париж", "correct": true, "scores": 10 },
              { "slug": "lyon", "label": "Лион", "correct": false, "scores": 0 }
            ],
            "validators": [{ "type": "required" }]
          },
          {
            "type": "enum",
            "widget": "radio",
            "label": "Столица Японии?",
            "slug": "q2_japan_capital",
            "has_quiz": true,
            "items": [
              { "slug": "tokyo", "label": "Токио", "correct": true, "scores": 10 },
              { "slug": "osaka", "label": "Осака", "correct": false, "scores": 0 }
            ],
            "validators": [{ "type": "required" }]
          },
          {
            "type": "string",
            "label": "Назовите самый большой океан",
            "slug": "q3_ocean",
            "has_quiz": true,
            "quiz_items": [
              { "label": "Тихий", "correct": true, "scores": 10 },
              { "label": "Тихий океан", "correct": true, "scores": 10 }
            ],
            "validators": [{ "type": "required" }]
          }
        ]
      }
    ]
  }
}
```
