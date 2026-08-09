---
name: femida
description: >
  Работа с кандидатами в Femida через локальный stdlib-only CLI без внешних Python-зависимостей.
  Используй скилл при запросах: найти кандидата, открыть карточку кандидата,
  получить notes/messages/offers/salary costs/dismissed feedback, скачать резюме
  или другое вложение, посмотреть интервью, собрать список кандидатов по текстовому
  поиску, вакансии, команде или подразделению, посчитать кандидатов, построить
  воронку найма или сделать аналитику по секциям.
  Триггерится на: "femida", "фемида", "candidate", "кандидат", "найди кандидата",
  "поиск кандидатов", "resume", "резюме", "скачай резюме", "notes", "offers",
  "salary costs", "dismissed feedback", "interview", "recruiter", "рекрутер",
  "сколько активных кандидатов", "воронка найма", "секции", "analytics".
---

# Femida Skill

Скилл для безопасной и предсказуемой работы с Femida через `scripts/femida_tool.py`.

## Когда использовать

- Поиск кандидатов по свободному тексту, вакансии, команде, стеку, ФИО.
- Получение карточки кандидата по `id`.
- Получение `notes`, `messages`, `offers`, `salary_costs`, `dismissed_feedback`.
- Получение данных интервью по `interview id`.
- Скачивание резюме и других вложений кандидата.
- Подсчёт кандидатов по выборке, срезы по воронке и аналитика по секциям.

## Когда не использовать

- Создание или изменение вакансий, откликов, статусов найма, bulk-операции.
- Tracker, Wiki, DataLens, YT, Arcadia VCS.
- Любые внешние модели или внешние сервисы: Femida содержит NDA и PII-данные.

## Preconditions

```bash
export FEMIDA_TOKEN_FILE="<path from AGENTS.md>"
# optional fallback
export FEMIDA_TOKEN="<OAuth token>"
# optional
export FEMIDA_BASE_URL="https://femida.yandex-team.ru/api"
export FEMIDA_AUTH_SCHEME="oauth"
```

Правило токена:
- сначала использовать `FEMIDA_TOKEN_FILE` из активного `AGENTS.md`;
- `scripts/femida_tool.py` умеет сам читать токен из `FEMIDA_TOKEN_FILE`;
- не искать токен Femida в `~/Desktop/tokens.txt` и других файлах;
- если файл отсутствует, пустой или токен невалиден, остановиться и сообщить об этом пользователю.

Ограничения среды:
- для работы нужен доступ во внутреннюю сеть Яндекса;
- локальный MCP-сервер Femida лежит в `~/arcadia/ml/infra/model_context_protocol/servers/femida`;
- текущий поиск идёт через `POST /api/candidates/search/v2` с `text` и пагинацией через `page`;
- серверные `count` для некоторых неофициальных фильтров (`is_available`, `status` и похожих) могут быть нестабильными, поэтому аналитику нужно строить по фактически выгруженным кандидатам, а не по таким `count`.

## Порядок работы

1. Определить, что именно нужно пользователю:
   - поиск кандидатов;
   - карточка кандидата;
   - заметки/сообщения/офферы;
   - интервью;
   - вложение;
   - аналитика.
2. Для поиска сначала использовать узкий текст:
   - точное ФИО;
   - `candidate id`;
   - название команды/вакансии;
   - стек и домен вместе (`python райдтех`, `sre лавка`);
   - для команды/подразделения пробовать 2-4 текстовых варианта и явно писать, что выборка текстовая, а не оргструктурная.
3. Для точных count/аналитики использовать агрегатные команды:
   - `CountCandidates` для количества и разных определений "active";
   - `SummarizeFunnel` для воронки;
   - `SummarizeSections` для секций;
   - `TopCandidatesBySections` для списка сильных кандидатов;
   - по умолчанию эти команды должны идти с `all_pages=true` и `dedupe=true`, а для очень широких запросов можно ограничить `max_pages` и явно пометить результат как частичный.
4. После поиска открывать карточку кандидата только если действительно нужны детали по конкретному человеку:
   - проверить `id`, ФИО, `status`, `extended_status`, `attachments`, `applications`.
5. Только после проверки карточки читать более чувствительные данные:
   - `notes`, `messages`, `offers`, `dismissed_feedback`, `salary_costs`.
6. Для скачивания резюме сначала посмотреть `attachments` в карточке кандидата, затем скачать нужный `attachment_id`.
7. Для интервью сначала взять `interview id` из карточки кандидата или из запроса пользователя, затем вызвать `GetInterview`.
8. Для аналитики всегда дедуплицировать кандидатов по `candidate id`, иначе выборка может содержать дубли.

## Что считать "active"

- `is_available=true`: кандидат доступен по поисковой выдаче. Это лучший сигнал для "доступен сейчас".
- `status=in_progress`: у кандидата есть текущее рассмотрение в процессе.
- `active applications > 0`: есть хотя бы один активный application.
- Если пользователь говорит просто "активные", по умолчанию показывать все три числа и коротко объяснять различие.

## Безопасные правила

- Не показывать телефоны, почты, Telegram, заметки и переписку без явного запроса пользователя.
- Для `notes` и `messages` по умолчанию пересказывать суть, а не отдавать длинные verbatim-дампы.
- Не делать вывод "кандидат доступен" только по `status` карточки:
  использовать `is_available` из поисковой выдачи, если он есть, и явно отмечать, когда это вывод по косвенным признакам.
- `SearchCandidate` по умолчанию не должен тащить `passages`, а `GetCandidate` по умолчанию не должен раскрывать `contacts`.
- Параметр `only_available` в `SearchCandidate` это локальный фильтр по уже выгруженным страницам, а не надежный серверный фильтр для `count`.
- Перед скачиванием вложения перепроверять, что `attachment_id` относится к нужному кандидату.
- Если аналитика построена не по всем страницам или уперлась в `max_pages`, честно писать об ограничении, а не называть результат "полным".

## Запуск

```bash
python3 scripts/femida_tool.py <ToolName> --params '{"text":"райдтех"}'
python3 scripts/femida_tool.py <ToolName> --params-file /tmp/params.json
python3 scripts/femida_tool.py SearchCandidate --print-tool-list
```

## Инструменты

- `SearchCandidate`
- `CountCandidates`
- `SummarizeFunnel`
- `SummarizeSections`
- `TopCandidatesBySections`
- `GetCandidate`
- `GetCandidateNotes`
- `GetCandidateSalaryCosts`
- `GetCandidateDismissedFeedback`
- `GetCandidateMessages`
- `GetCandidateOffers`
- `GetInterview`
- `DownloadAttachment`

## Быстрые примеры

```bash
python3 scripts/femida_tool.py SearchCandidate --params '{"text":"python райдтех","limit":10}'
python3 scripts/femida_tool.py SearchCandidate --params '{"text":"backend райдтех","all_pages":true,"dedupe":true,"limit":20}'
python3 scripts/femida_tool.py CountCandidates --params '{"text":"backend райдтех","all_pages":true}'
python3 scripts/femida_tool.py SummarizeFunnel --params '{"text":"backend райдтех","all_pages":true}'
python3 scripts/femida_tool.py SummarizeSections --params '{"text":"backend райдтех","all_pages":true}'
python3 scripts/femida_tool.py TopCandidatesBySections --params '{"text":"backend райдтех","all_pages":true,"status":"in_progress","limit":5}'
python3 scripts/femida_tool.py GetCandidate --params '{"id":202597713}'
python3 scripts/femida_tool.py GetCandidate --params '{"id":202597713,"include_contacts":true}'
python3 scripts/femida_tool.py GetCandidateNotes --params '{"id":202597713,"limit":5}'
python3 scripts/femida_tool.py GetCandidateMessages --params '{"id":202597713,"limit":20}'
python3 scripts/femida_tool.py GetCandidateOffers --params '{"id":202597713}'
python3 scripts/femida_tool.py GetInterview --params '{"id":1221991}'
python3 scripts/femida_tool.py DownloadAttachment --params '{"id":9925463}'
```

## Типовые запросы

- "Сколько активных кандидатов?"
  Используй `CountCandidates` и показывай три метрики: `available`, `in_progress`, `with_active_applications`.
- "Покажи воронку найма по выборке"
  Используй `SummarizeFunnel`.
- "Дай срез по секциям"
  Используй `SummarizeSections`.
- "Кто самые сильные по секциям?"
  Используй `TopCandidatesBySections`.
- "Покажи только тех, кто еще в процессе"
  Используй `TopCandidatesBySections` с `status="in_progress"`.
- "Найди кандидатов по стеку и домену"
  Используй `SearchCandidate` с узким текстом вида `python райдтех`, `go fintech`, `sre лавка`.

Канонические команды:

```bash
python3 scripts/femida_tool.py CountCandidates --params '{"text":"backend райдтех"}'
python3 scripts/femida_tool.py SummarizeFunnel --params '{"text":"backend райдтех"}'
python3 scripts/femida_tool.py SummarizeSections --params '{"text":"backend райдтех"}'
python3 scripts/femida_tool.py TopCandidatesBySections --params '{"text":"backend райдтех","limit":5}'
python3 scripts/femida_tool.py TopCandidatesBySections --params '{"text":"backend райдтех","status":"in_progress","limit":5}'
python3 scripts/femida_tool.py SearchCandidate --params '{"text":"python райдтех","limit":10}'
```

## Что должно быть в ответе пользователю

- Какая команда выполнена и по каким параметрам.
- Какие кандидаты / карточки / интервью / вложения были прочитаны или агрегированы.
- Где ответ точный, а где есть ограничение по поиску или пагинации.
- Для аналитики:
  по какой текстовой выборке она построена, были ли дубликаты, сколько страниц реально обошли, и что именно считается "active" или "прошёл секцию".
- Для изменяемых или чувствительных сущностей:
  что именно было запрошено и почему этого достаточно для ответа.
