---
name: guru-break-nile-2-yql
description: Мигрировать extractors/transforms в microbatch_from_hist со старого Nile-стиля на новый YQL transfilter DSL. Вызывать, когда пользователь просит мигрировать экстракторы, перевести на transfilter или перейти с Nile на YQL.
argument-hint: <путь-к-директории>
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

# Миграция Nile -> YQL (transfilter DSL)

Мигрировать экстракторы и трансформы в `microbatch_from_hist` со старого Nile-стиля на новый YQL transfilter DSL (`dmp_suite.libs.yql.transfilter.transform`).

## Использование

```
/nile-2-yql services/demand_etl/demand_etl/layer/yt/ods/crm_admin/campaign/
```

Аргумент — путь к директории. Мигрировать все вызовы `microbatch_from_hist` внутри этой директории и её поддиректорий. НЕ трогать `circuit_microbatch_from_hist`.

## Порядок работы

1. Найти все `loader.py` с `microbatch_from_hist` в указанной директории
2. Для каждого loader проверить соответствующий `impl.py` — **если в нём есть импорты из `dmp_suite.utils`, пропустить эту таску целиком**
3. Прочитать loader и impl, чтобы понять текущие extractors и transforms
4. Применить правила миграции (ниже)
5. Проверить, что изменённые файлы корректно импортируются: `python -c 'import <module_path>'`
6. Отчитаться: что мигрировано, что пропущено, какие непокрытые паттерны встретились

## Контекст: старая и новая системы

### Старая система (мигрируем С неё)

**Extractors** — это `dict[str, ExtractorType]`, где значения могут быть:
- Простые строки: `'ods_field': 'raw_field'` (путь в doc)
- `eu.path_extractor('path', default_value=X, converter=func)` из `dmp_suite.utils.extract_utils`
- `eu.coalesce_extractor('field1', 'field2')` — возвращает первое не-None значение
- Callable `(doc, field_name) -> value` или `(doc) -> value`

**Transforms** из `dmp_suite.data_transform.transform`:
- `Map(func)` — преобразование 1-к-1, `func(doc) -> dict`
- `FlatMap(func)` — преобразование 1-к-N, `func(doc) -> Iterable[dict]` (часто через `yield`)
- `Filter(func)` — предикат, `func(doc) -> bool`
- Цепочки через `|`: `Filter(f) | FlatMap(g)`

### Новая система (мигрируем НА неё)

Импорт: `import dmp_suite.libs.yql.transfilter.transform as tf`

**Extractors** через модификатор `tf.from_doc(...)`:
```python
EXTRACTORS_YQL = tf.from_doc(
    ods_field='raw_field',                                    # простой путь из doc
    typed_field=tf.doc_path_extractor('path', auto_convert=True),  # с приведением типа
    computed=tf.pyfunc(my_func, outtype=String)(tf.col('x')),     # Python UDF
    yql_computed=tf.yqlfunc(inline="($x) -> { ... }")(tf.col('x')),  # YQL-лямбда
    stdlib_computed=tf.yqlfunc(from_stdlib="String::AsciiToLower")(tf.col('name')),
)
```

**Transforms** оставляем на Python через `pyfunc`. НЕ переписывать логику трансформов на YQL:
```python
transform=tf.Map(tf.pyfunc(mapper_yql))(tf.col('doc'))
transform=tf.FlatMap(tf.pyfunc(flattener_yql))(tf.col('doc'))
transform=tf.Filter(tf.pyfunc(pred_yql))(tf.col('doc'))
```

## Ключевое правило: EXTRACTORS_YQL

**Не заменять** существующий словарь `EXTRACTORS`. Создать **новую копию** с именем `EXTRACTORS_YQL`, потому что старый `EXTRACTORS` может использоваться другими тасками.

```python
# Старый словарь — НЕ ТРОГАТЬ, НЕ УДАЛЯТЬ
EXTRACTORS = dict(
    campaign_id='id',
    campaign_name='name',
)

# Новый словарь — создать рядом
EXTRACTORS_YQL = tf.from_doc(
    campaign_id='id',
    campaign_name='name',
)

# Поменять только вызов microbatch_from_hist:
task = microbatch_from_hist(
    ...
    extractors=EXTRACTORS_YQL,  # было EXTRACTORS
    ...
)
```

Если extractors определены inline в `microbatch_from_hist(extractors=dict(...))`, вынести их в отдельную переменную `EXTRACTORS_YQL`.

## Правило пропуска

Перед миграцией таски проверить соответствующий `impl.py` (если он есть). **Если в `impl.py` есть импорты из `dmp_suite.utils`** (например, `from dmp_suite.utils import extract_utils`, `from dmp_suite.utils import datetime_utils`), **пропустить эту таску целиком**. Такие таски используют утилиты, требующие отдельной обработки, и будут мигрированы позже.

## Fallback: непокрытые паттерны

Если встретился экстрактор или трансформ, который не попадает ни под одно из правил ниже (например, кастомный callable-экстрактор, нестандартный класс, сложная композиция), — **пропустить этот экстрактор/таску и сообщить пользователю**. Не пытаться угадывать миграцию для незнакомых паттернов.

## Правила миграции

### Правило 1: Простые строковые экстракторы

```python
# БЫЛО
EXTRACTORS = dict(campaign_id='id', campaign_name='name')

# СТАЛО (добавить рядом, НЕ удалять EXTRACTORS)
EXTRACTORS_YQL = tf.from_doc(campaign_id='id', campaign_name='name')
```

Строки внутри `from_doc()` автоматически трактуются как `doc_path_extractor`.

### Правило 2: `eu.path_extractor('field')` без converter и default

```python
# БЫЛО
'my_field': eu.path_extractor('nested.path')

# СТАЛО (внутри tf.from_doc)
my_field='nested.path'
# или явно:
my_field=tf.doc_path_extractor('nested.path')
```

**Внимание:** `eu.path_extractor` поддерживает числовые индексы в пути (например, `'items.0.name'` для доступа к первому элементу списка). `tf.doc_path_extractor` такие пути тоже поддерживает — каждый сегмент пути становится ключом Yson-словаря. Однако если семантика доступа по индексу в массиве критична, проверить, что результат эквивалентен, или пропустить этот экстрактор (см. Fallback).

### Правило 3: `eu.path_extractor('field', default_value=X)`

```python
# БЫЛО
'planned_channels': eu.path_extractor('planned_channels', default_value=[])

# СТАЛО — YQL COALESCE через inline yqlfunc:
planned_channels=tf.yqlfunc(
    inline="($x) -> { RETURN COALESCE(Yson::ConvertToList($x), AsList()) }"
)(tf.doc_path_extractor('planned_channels'))
```

Для скалярных значений по умолчанию:
```python
# default_value=None — естественное поведение, менять не нужно
my_field='my_field'

# default_value=''
my_field=tf.yqlfunc(
    inline="($x) -> { RETURN COALESCE(Yson::ConvertToString($x), '') }"
)(tf.doc_path_extractor('my_field'))
```

### Правило 4: `eu.path_extractor('field', converter=func)`

#### 4a: `converter=dtu.format_datetime` или `converter=dtu.format_datetime_wo_delimiter`

```python
# БЫЛО
'utc_created_dttm': eu.path_extractor('created_at', converter=dtu.format_datetime_wo_delimiter)

# СТАЛО — inline YQL форматирование даты:
utc_created_dttm=tf.yqlfunc(
    inline="""($x) -> {
        $s = Yson::ConvertToString($x, Yson::Options(true as AutoConvert));
        RETURN DateTime::Format('%Y-%m-%d %H:%M:%S')(
            DateTime::MakeDatetime(DateTime::ParseIso8601($s))
        );
    }"""
)(tf.doc_path_extractor('created_at'))
```

Обе функции (`format_datetime` и `format_datetime_wo_delimiter`) на практике возвращают один и тот же формат `YYYY-MM-DD HH:MM:SS`, поэтому YQL-код одинаковый.

Дублирование inline YQL между файлами допустимо. Общая библиотека UDF будет создана позже.

#### 4b: `converter=json.loads`

```python
# БЫЛО
'data_dict': eu.path_extractor('data', converter=json.loads)

# СТАЛО
data_dict=tf.json_loads(tf.doc_path_extractor('data'))
```

#### 4c: `converter=TYPE` (тип как конвертер, например `str`, `int`, `float`, `bool`)

Использовать `tf.cast` с соответствующим YT-типом:

```python
# БЫЛО
'my_field': eu.path_extractor('field', converter=str)
# СТАЛО
my_field=tf.cast('field', as_type=String)

# БЫЛО
'count': eu.path_extractor('count', converter=int)
# СТАЛО
count=tf.cast('count', as_type=Int)
```

Таблица соответствия типов:
| Python-тип | YT-тип (из `dmp_suite.yt.model`) |
|------------|-----------------------------------|
| `str`      | `String`                          |
| `int`      | `Int`                             |
| `float`    | `Double`                          |
| `bool`     | `Boolean`                         |

Внутри `tf.from_doc(...)` вызов `tf.cast('field', as_type=T)` автоматически оборачивает строку в `doc_path_extractor('field')`.

#### 4d: `converter=lambda x: <выражение>`

Решать по ситуации:
- Простые лямбды -> inline yqlfunc
- Сложные лямбды с Python-логикой -> `tf.pyfunc(lambda_func, outtype=TargetType)`

```python
# БЫЛО (простой случай)
'field': eu.path_extractor('field', converter=lambda x: None if x == '' else x)
# СТАЛО (YQL)
field=tf.yqlfunc(
    inline="($x) -> { $s = Yson::ConvertToString($x); RETURN IF($s = '', NULL, $s) }"
)(tf.doc_path_extractor('field'))

# БЫЛО (сложный случай)
'segment_id': eu.path_extractor('yt_path', converter=lambda s: s.split('/')[-1])
# СТАЛО (pyfunc)
segment_id=tf.pyfunc(lambda s: s.split('/')[-1], outtype=String)(tf.doc_path_extractor('yt_path'))
```

### Правило 5: `eu.coalesce_extractor('field1', 'field2')`

```python
# БЫЛО
'utc_start': eu.coalesce_extractor('efficiency_start_time', 'regular_start_time')

# СТАЛО
utc_start=tf.yqlfunc(
    inline="($a, $b) -> { RETURN COALESCE(Yson::ConvertToString($a), Yson::ConvertToString($b)) }"
)(tf.doc_path_extractor('efficiency_start_time'), tf.doc_path_extractor('regular_start_time'))
```

### Правило 6: Адаптация Python-функций в `impl.py` для `pyfunc`

При оборачивании существующей Python-функции (mapper, filter, flatmapper) в `pyfunc`, функция получает сырые байты из YQL вместо распарсенного dict. Нужно добавить `yson.loads()` в начале и `yson.dumps()` вокруг возвращаемого значения.

Импорт yson: `from yt import yson`

**Создавать новые функции с суффиксом `_yql` рядом со старыми. НЕ модифицировать оригиналы.**

Для Map:
```python
# БЫЛО (impl.py)
def mapper(doc):
    return dict(
        state_id=doc.get('id'),
        campaign_id=doc.get('campaign_id'),
        utc_state_dttm=msk_to_utc(doc.get('updated_at')),
    )

# СТАЛО (impl.py) — добавить yson.loads/yson.dumps:
from yt import yson

def mapper_yql(doc):
    doc = yson.loads(doc)
    return yson.dumps(dict(
        state_id=doc.get('id'),
        campaign_id=doc.get('campaign_id'),
        utc_state_dttm=msk_to_utc(doc.get('updated_at')),
    ))
```

Для FlatMap (генераторы с `yield`):
```python
# БЫЛО (impl.py)
def mapper(doc):
    for item in doc.get('items', []):
        yield dict(item_id=item.get('id'), name=item.get('name'))

# СТАЛО (impl.py):
from yt import yson

def mapper_yql(doc):
    doc = yson.loads(doc)
    for item in doc.get('items', []):
        yield yson.dumps(dict(item_id=item.get('id'), name=item.get('name')))
```

Для Filter (предикаты):
```python
# БЫЛО (impl.py)
def filter_func(doc):
    return doc.get('name') == 'input_schema'

# СТАЛО (impl.py):
from yt import yson

def filter_func_yql(doc):
    doc = yson.loads(doc)
    return doc.get('name') == 'input_schema'
```

### Правило 7: Трансформ `Map(mapper)`

Трансформы оставлять на Python. Не переписывать логику mapper на YQL.

```python
# БЫЛО (loader.py)
microbatch_from_hist(..., extractors={}, transform=Map(mapper))

# СТАЛО (loader.py) — использовать адаптированный mapper_yql из impl.py:
microbatch_from_hist(..., extractors=None, transform=tf.Map(tf.pyfunc(mapper_yql))(tf.col('doc')))
```

Если mapper достаточно прост (только `doc.get()` без сложной логики), можно конвертировать в extractors:
```python
EXTRACTORS_YQL = tf.from_doc(
    state_id='id',
    campaign_id='campaign_id',
    utc_state_dttm=tf.pyfunc(msk_to_utc, outtype=String)(tf.doc_path_extractor('updated_at')),
)
microbatch_from_hist(..., extractors=EXTRACTORS_YQL, transform=None)
```

### Правило 8: Трансформ `FlatMap(mapper)`

```python
# БЫЛО
microbatch_from_hist(..., extractors={}, transform=FlatMap(mapper))

# СТАЛО — использовать адаптированный mapper_yql из impl.py:
microbatch_from_hist(..., extractors=None, transform=tf.FlatMap(tf.pyfunc(mapper_yql))(tf.col('doc')))
```

### Правило 9: Трансформ `Filter(predicate)`

```python
# БЫЛО
microbatch_from_hist(..., transform=Filter(filter_func))

# СТАЛО — использовать адаптированный filter_func_yql из impl.py:
microbatch_from_hist(..., transform=tf.Filter(tf.pyfunc(filter_func_yql))(tf.col('doc')))
```

### Правило 10: Цепочки трансформов `Filter(...) | FlatMap(...)`

**НЕ переписывать.** Объединить в один pyfunc:

```python
# БЫЛО
transform=Filter(filter_func) | FlatMap(mapper)

# СТАЛО — объединить в один pyfunc с yson-обёрткой:
from yt import yson

def filtered_mapper_yql(doc):
    doc = yson.loads(doc)
    if not filter_func(doc):
        return
    for result in mapper(doc):
        yield yson.dumps(result)

transform=tf.FlatMap(tf.pyfunc(filtered_mapper_yql))(tf.col('doc'))
```

### Правило 11: Пустые extractors `{}`

Когда `extractors={}` и вся логика в `transform`:
- Если transform — простой Map, можно конвертировать в extractors (Правило 7)
- Если transform — FlatMap/Filter или сложный Map, обернуть в pyfunc (Правила 8-9)
- В обоих случаях заменить пустой dict `{}` на `None`

## Важные замечания

- **Добавить импорт:** `import dmp_suite.libs.yql.transfilter.transform as tf`
- **НЕ удалять старые импорты:** Старые импорты (`extract_utils`, `Map`, `FlatMap`, `Filter`) НЕ удалять — они могут использоваться другим кодом в файле или другими модулями, импортирующими из этого файла.
- **НЕ менять:** Имя таски, ссылки на таблицы, параметры `backfill_*`, `updated_field`, `key_fields`, `pool`, `intensity`, шедулеры и любые другие параметры, не связанные с extractors/transform.
- **`from_doc` vs `as_is`:** Использовать `tf.from_doc(...)`, когда экстракторы обращаются к полям doc (строки автоматически оборачиваются в `doc_path_extractor`). Использовать `tf.as_is(...)` только когда экстракторы обращаются к сырым колонкам напрямую (не вложенным в doc).
- **pyfunc требует outtype:** Всегда указывать `outtype` для `pyfunc`. Брать из типа поля ODS-таблицы: `String` -> `String`, `Int` -> `Int`, `Datetime` -> `String` (форматированный) и т.д. Типы импортировать из `dmp_suite.yt.model`.
- **EXTRACTORS_YQL:** Всегда создавать новую переменную `EXTRACTORS_YQL`, не модифицировать существующую `EXTRACTORS`.
- **Дублирование YQL-кода допустимо:** Дублирование inline YQL-лямбд между файлами допускается. Не создавать shared UDF файлы.
- **Когда `EXTRACTORS` импортируется из другого модуля** (например, `from ..loader import EXTRACTORS`): создать `EXTRACTORS_YQL` в том же модуле-источнике и импортировать оттуда.

## Таблица выбора: yqlfunc vs pyfunc

| Случай | Что использовать |
|--------|------------------|
| Простое переименование поля | `tf.from_doc(new='old')` — функция не нужна |
| Извлечение с auto_convert | `tf.doc_path_extractor('path', auto_convert=True)` |
| Форматирование даты | `yqlfunc` (inline DateTime:: YQL) |
| COALESCE / обработка NULL | `yqlfunc` (inline COALESCE) |
| `json.loads` | `tf.json_loads()` |
| Тип как конвертер (`str`, `int` и т.д.) | `tf.cast('field', as_type=YTType)` |
| Простое сравнение/булево | `yqlfunc` (inline лямбда) |
| Разбиение строк, regex, сложный парсинг | `pyfunc` |
| Трансформы Map/FlatMap/Filter | `pyfunc` (оставить Python-логику как есть) |
| Цепочки трансформов (`\|`) | Объединить в один `pyfunc`, не переписывать на YQL |
| Конвертация таймзон (pytz) | `pyfunc` (оставить Python-логику) |
| Сложные многошаговые вычисления | `pyfunc` |

## Справка: рабочий пример

См. `services/bluecollars_etl/bluecollars_etl/layer/yt/ods/yacrm_smena/` — лоадеры, уже использующие новый transfilter DSL с `tf.from_doc()` и `microbatch_from_hist`.
