---
name: create-course
description: "Заводит мультиязычный курс в LMS через Django-admin (только testing) по правилам тестовых курсов: slug slug_tmslv{id}, название TMSLV{id} {КОД}, флаг мультиязычности, языки в порядке из ТК, карточка (название/кому подойдёт/чему научитесь) на каждый язык, куратор, модули-статьи, публикация. Используй в связке со скиллом tms: сначала прочитать TMS-кейс, затем на его основе создать курс. Триггеры: «заведи/создай курс», «мультиязычный курс», «курс по кейсу», slug_tmslv, TMSLV."
allowed-tools: Bash(node:*)
user-invocable: true
---

Создаёт МЯ-курс в LMS через Django-admin `testing.admin.lms.yandex-team.ru`, драйвя формы браузером
под `storageState` робота (как `*.mjs` в корне проекта LMS). Запускать из директории проекта LMS
(или задать `LMS_PROJECT_DIR`) — оттуда берутся `@playwright/test` и куки робота.

## Вызов как слэш-команда `/create-course <аргументы>`

Если аргумент — **номер TMS-кейса** (напр. `/create-course 876`), выполни весь сценарий:
1. Прочитай кейс: `~/.claude/skills/tms/scripts/tms-cli.sh get <id> --project lm`.
2. Извлеки из ТК: **языки и их порядок** (из «…с 2-мя языками: RU, EN»), **публикацию**
   («опубликованный»→`--publish`, «НЕопубликованный»→`--no-publish`), **число модулей** (дефолт 2).
   Если кейс описывает несколько курсов — запусти на каждый со своим `--count` (1, 2, …):
   он даёт slug `slug_tmslv{id}_{count}` и имя `TMSLV{id}_{count} {КОД}` (номер попадает в каждый язык).
3. Прогони **dry-run** (без `--apply`) и покажи план пользователю.
4. Спроси куратора, если не задан (по умолчанию предложи `yusokolova`).
5. После подтверждения — повтори с `--apply`. Затем дай ссылку на курс в admin.

Если переданы явные флаги (`--tms-id …`) — просто прокинь их в CLI ниже.
Всегда сначала dry-run, `--apply` — только после явного «ок».

CLI: `node <skill>/scripts/create-course.mjs <опции>`

```
--tms-id N            номер TMS-кейса → slug=slug_tmslv{N}, name=TMSLV{N}
--count K             порядковый № курса в кейсе (когда курсов несколько):
                      slug=slug_tmslv{N}_{K}, name=TMSLV{N}_{K} {КОД} в каждом языке.
                      Без флага (один курс) — суффикса нет.
--languages ru,en     коды языков В ПОРЯДКЕ из ТК (важно)
--curator LOGIN       логин куратора/автора; по умолчанию robot-lms-hermione. id резолвится сам
--publish             опубликовать (is_active+show_in_catalog+show_in_lab)
--no-publish          оставить черновиком
--modules SPEC        число (N статей) ИЛИ список типов через запятую: "article,article,video".
                      Поддержаны article|video (по умолчанию 2 статьи). scorm — НЕ поддержан
                      (форма admin требует загрузку пакета; создать вручную).
--category NAME|ID    категория (M2M «Категории»/coursecategory); по умолчанию «Языки программирования».
                      Каскадной ПОДкатегории (как в конструкторе Лабы) в admin нет — задаётся только категория.
--study-mode ID       форма обучения (по умолчанию 37 = Самостоятельно)
--start-mode MODE     «обучение от»: any_time (деф.) | after_group_filled | fixed_dates
--payment MODE        способ оплаты: free (деф.) | corporate | personal
--name-base BASE      префикс имени (по умолчанию TMSLV)
--slug SLUG           переопределить slug
--force               удалить существующий курс с таким slug перед созданием
--apply               РЕАЛЬНО создать. Без него — DRY-RUN (только печать плана)
```

Заполняемые поля (все обязательные): название/«кому подойдёт»/«чему научитесь» на КАЖДОМ языке,
куратор курса, категория, форма обучения, «обучение от», способ оплаты, языки, публикация.
Модули заполняются на всех языках: **статья** — название+контент+продолжительность;
**видео** — название+продолжительность (url — placeholder `https://example.com/replace-me`,
реальную ссылку пользователь приложит сам).

## Рабочий процесс (связка со скиллом `tms`)

1. Прочитать кейс: `tms` → `get <id> --project lm`.
2. Из ТК определить параметры (это делает агент, глядя в кейс):
   - **языки и порядок** — из предусловий («…с 2-мя языками: RU, EN»);
   - **публикация** — из формулировки («опубликованный» → `--publish`, «НЕопубликованный» → `--no-publish`);
   - **модули** — из описания («состоит из N модулей: Видео/Статья»); тип → `--modules article,video`;
     дефолт — 2 статьи. scorm автосозданием не поддержан.
   - Если кейс описывает НЕСКОЛЬКО курсов (напр. пары RU/EN и AB/DE) — вызвать скилл на каждый набор
     со своим `--count` (1, 2, …), чтобы slug и имя были уникальны и пронумерованы.
3. Прогнать **dry-run** (без `--apply`), показать план пользователю.
4. После подтверждения — тот же вызов с `--apply`.

Пример:
```bash
# по кейсу 887 (RU/EN, опубликованный, 1 видео-модуль → 2 статьи по дефолту)
node scripts/create-course.mjs --tms-id 887 --languages ru,en --curator yusokolova --publish
node scripts/create-course.mjs --tms-id 887 --languages ru,en --curator yusokolova --publish --apply
```

## Ключевые факты механики (проверено на реальном создании)

- **Порядок обязателен**: курс создаётся ЧЕРНОВИКОМ (`structure=no_modules`, не активен) → языки → карточка →
  outcomes → модули → и только в конце `structure=multi_modules` + публикация. Иначе бэк отвечает
  «У курса должны быть модули».
- Поле `course` в admin-моделях (`courselanguage`, `coursecontent`, `textresource`) принимает **числовой id
  курса**, не slug.
- В content-моделях (`coursecontent`, `courselearningoutcomescontent`) поле `course_language` — это **pk записи
  CourseLanguage**, не код языка. Скилл резолвит его через `courselanguage/?course=ID&language=CODE`.
- Куратор — inline `tutor-0-user` в форме курса; `author` и `tutor.user` — FK на `/admin/users/user/`
  (id по логину: `?q=<login>`). «Чему научитесь» — родитель `learning_outcomes` (OneToOne, pk = id курса).
- Категория — `filter_horizontal` виджет: выбор через `#id_categories_from` + клик `#id_categories_add_link`
  (обычный `selectOption('#id_categories')` таймаутит — select скрыт). В admin только категория, без подкатегории.
- Модули: article = `resources/textresource` (+`editor_type=yfm`, иначе не виден в Лабе),
  video = `resources/videoresource` (обязателен `url`). Переводы — `*content` per язык, `course_language`=pk.
  `id` модуля в changelist берётся из текста ссылки на change (первая колонка — чекбокс).

## Требования и безопасность

- Только **testing**. Куки робота: `tests/playwright/tests/auth/teardownUser.json` (протухли → обновить
  `auth.setup` с `LMS_ROBOT_HERMIONE_PASSWORD`).
- **Dry-run по умолчанию** — запись только с `--apply`. Есть pre-check: не перезатирает существующий slug.
- Полную карту admin-моделей см. в памяти проекта (lms-admin-course-creation).
