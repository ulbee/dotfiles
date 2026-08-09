use mtsmart;
PRAGMA skip_unavailable_shards = 1;

select
    min(EventDateTime) as minTime,
    max(EventDateTime) as maxTime,
    groupUniqArray(DeviceID) as appmetrica_device_id,
    groupUniqArray(AppVersionName) as version
from mobgiga.events_all
WHERE
    APIKey = 2998081
    and EventName = 'ui_event'
    and EventDate = '{{EVENT_DATE}}'
    and arrayFilter((x3, x2, x1) -> (x1 like 'CommonParams') and (x2 like 'executorId'), ParsedParams.Key3, ParsedParams.Key2, ParsedParams.Key1)[1] in (
            '{{EXECUTOR_ID}}'
    )
group by UUID
order by (minTime, maxTime)
limit 100
