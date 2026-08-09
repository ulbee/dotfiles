use mtsmart;
PRAGMA skip_unavailable_shards = 1;

select
    EventDateTime,
    EventName,
    ParsedParams.Key1,
    ParsedParams.Key2,
    ParsedParams.Key3,
    ParsedParams.Key4,
    arrayFilter((x3, x2, x1) -> (x1 != 'CommonParams') AND (x2 = 'url'), ParsedParams.Key3, ParsedParams.Key2, ParsedParams.Key1)[1] as url,
    arrayFilter((x1) -> (x1 != 'CommonParams'), ParsedParams.Key1) as _key1,
    arrayFilter((x2, x1) -> (x1 != 'CommonParams'), ParsedParams.Key2, ParsedParams.Key1) as _key2,
    arrayFilter((x3, x2, x1) -> (x1 != 'CommonParams'), ParsedParams.Key3, ParsedParams.Key2, ParsedParams.Key1) as _key3,
    arrayFilter((x4, x3, x2, x1) -> (x1 != 'CommonParams'), ParsedParams.Key4, ParsedParams.Key3, ParsedParams.Key2, ParsedParams.Key1) as _key4
FROM mobgiga.events_all
PREWHERE
    EventDate = '{{EVENT_DATE}}'
    and DeviceIDHash = sipHash64('{{DEVICE_ID}}')
    {{DATETIME_FILTER}}
WHERE
    APIKey = {{API_KEY}}
ORDER BY EventDateTime ASC
LIMIT 1000
