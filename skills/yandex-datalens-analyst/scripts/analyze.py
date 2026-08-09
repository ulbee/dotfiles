#!/usr/bin/env python3
"""
DataLens Dashboard Analyzer
Автоматический обход и анализ дашборда Yandex DataLens.

Использует два API:
  - Public API (api.datalens.yandex.net) — метаданные (структура, конфиг, датасеты)
  - Chart Data API (charts.yandex-team.ru) — фактические данные чартов

Использование:
    export DATALENS_OAUTH_TOKEN="<your-oauth-token>"
    python3 analyze.py <DASHBOARD_ID> [--output report.json]
    python3 analyze.py <DASHBOARD_ID> --list-charts
    python3 analyze.py --run-chart <CHART_ID> [--params '{"key": ["val"]}']
    python3 analyze.py --run-chart-with-tab-context <DASHBOARD_ID> <CHART_ID>
    python3 analyze.py --run-chart <CHART_ID> --value-at-period 2026-01 --aggregate stack-sum

Зависимости: только стандартная библиотека Python 3 (urllib).
"""

import os
import sys
import json
import ssl
import time
import re
import calendar
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any

API_HOST = "https://api.datalens.yandex.net"
CHARTS_HOST = "https://charts.yandex-team.ru"
DELAY = 0.15  # пауза между запросами (секунды)

# SSL: внутренние хосты Яндекса используют корпоративный CA,
# поэтому создаём контекст без проверки сертификатов.
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _resolve_token() -> str:
    """Найти OAuth-токен: env → token/.token рядом со скриптом → token/.token в cwd."""
    token = os.environ.get("DATALENS_OAUTH_TOKEN", "").strip()
    if token:
        return token
    # Ищем token/.token файл
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "token"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".token"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "token"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".token"),
        os.path.join(os.getcwd(), "token"),
        os.path.join(os.getcwd(), ".token"),
    ]
    for path in candidates:
        path = os.path.normpath(path)
        if os.path.isfile(path):
            with open(path, "r") as f:
                token = f.read().strip()
            if token:
                return token
    return ""


def _parse_token_file(filepath: str, key: str = "DATALENS_OAUTH_TOKEN") -> str:
    """Извлечь токен из файла. Поддерживает plain-text и multi-token KEY=\"value\" формат."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if "=" not in content:
        return content
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k == key:
            return v
    raise SystemExit(
        f"ОШИБКА: ключ {key} не найден в {filepath}. "
        f"Файл должен содержать строку вида {key}=\"<token>\" "
        f"или быть plain-text файлом с одним токеном."
    )


TOKEN = _resolve_token()
HEADERS = {
    "Authorization": f"OAuth {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "x-dl-api-version": "0",
}


def _http_post(url: str, headers: dict, body: dict) -> tuple[int, dict]:
    """HTTP POST с JSON-телом. Возвращает (status_code, parsed_json)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            return e.code, json.loads(body_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return e.code, {"error": f"http_{e.code}", "message": body_bytes[:200].decode("utf-8", errors="replace")}


def _rpc(method: str, body: dict) -> dict:
    """Вызвать RPC-метод публичного API DataLens."""
    time.sleep(DELAY)
    status, data = _http_post(f"{API_HOST}/rpc/{method}", HEADERS, body)
    if status in (403, 401, 404):
        return {"error": data.get("code", f"http_{status}"),
                "message": data.get("message", ""), "method": method}
    if status >= 400:
        return {"error": data.get("code", f"http_{status}"),
                "message": data.get("message", ""), "method": method}
    # Некоторые эндпоинты возвращают HTTP 200 с ошибкой в теле
    if isinstance(data, dict) and "code" in data and data.get("status", 200) >= 400:
        return {"error": data.get("code", "unknown"), "message": data.get("message", ""),
                "method": method}
    return data


def get_dashboard(dash_id: str) -> dict:
    """Получить дашборд."""
    result = _rpc("getDashboard", {"dashboardId": dash_id})
    if "entry" in result:
        return result["entry"]
    return result


def get_chart(chart_id: str) -> dict:
    """Получить чарт (пробует wizard, ql, editor)."""
    for method in ("getWizardChart", "getQLChart", "getEditorChart"):
        result = _rpc(method, {"chartId": chart_id})
        if "error" not in result:
            chart_type = method.replace("get", "").replace("Chart", "")
            # getEditorChart оборачивает ответ в {"entry": {...}}
            if "entry" in result and "data" in result["entry"]:
                entry = result["entry"]
                entry["_chart_type"] = chart_type
                return entry
            result["_chart_type"] = chart_type
            return result
    return {"error": "chart_not_found", "chartId": chart_id}


def inspect_chart(chart_id: str) -> dict:
    """Показать метаданные чарта: SQL, connection, placeholders, colors, params, фильтры."""
    chart = get_chart(chart_id)
    if "error" in chart:
        return chart
    data = chart.get("data", {})
    config = parse_chart_config(chart)
    viz = config.get("visualization", {})
    result: dict[str, Any] = {
        "chart_id": chart.get("entryId", chart_id),
        "chart_key": chart.get("key", ""),
        "chart_type": chart.get("_chart_type", ""),
        "visualization_type": viz.get("id", config.get("type", "")),
        "sql_query": data.get("queryValue"),
        "connection": data.get("connection"),
        "placeholders": [],
        "colors": [
            {"guid": c.get("guid"), "title": c.get("title"), "data_type": c.get("data_type")}
            for c in data.get("colors", [])
        ],
        "params": data.get("params", []),
        "fields": extract_fields(config),
        "filters": extract_filters(config),
    }
    for ph in viz.get("placeholders", []):
        result["placeholders"].append({
            "id": ph.get("id"),
            "items": [
                {"guid": item.get("guid"), "title": item.get("title"),
                 "data_type": item.get("data_type"), "type": item.get("type")}
                for item in ph.get("items", [])
            ],
        })
    return result


def get_dataset(dataset_id: str) -> dict:
    """Получить датасет."""
    return _rpc("getDataset", {"datasetId": dataset_id})


def get_connection(connection_id: str) -> dict:
    """Получить подключение."""
    return _rpc("getConnection", {"connectionId": connection_id})


# ---------------------------------------------------------------------------
# Chart Data API (charts.yandex-team.ru)
# ---------------------------------------------------------------------------

def run_chart(chart_id: str, params: dict | None = None) -> dict:
    """Выполнить чарт и получить фактические данные через Chart Data API."""
    time.sleep(DELAY)
    body: dict[str, Any] = {"id": chart_id, "params": params or {}}
    headers = {
        "Authorization": f"OAuth {TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
    }
    status, data = _http_post(f"{CHARTS_HOST}/api/run", headers, body)
    if status in (403, 401, 404):
        return {"error": data.get("code", f"http_{status}"),
                "message": data.get("message", "")}
    if status >= 400:
        return {"error": data.get("code", f"http_{status}"),
                "message": data.get("message", "")}
    return data


def _ts_to_date(ts_ms: int | float) -> str:
    """Конвертировать timestamp в миллисекундах в дату YYYY-MM-DD."""
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def parse_chart_data(run_response: dict) -> dict:
    """Извлечь данные из ответа /api/run в удобном для анализа формате."""
    data = run_response.get("data", {})
    result: dict[str, Any] = {
        "chart_id": run_response.get("id", ""),
        "chart_name": run_response.get("key", "").split("/")[-1],
        "chart_type": run_response.get("type", ""),
        "used_params": run_response.get("usedParams", run_response.get("params", {})),
    }

    # Metric widgets can return data as an array of tiles instead of an object.
    if isinstance(data, list):
        metrics: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            content = item.get("content", {})
            current = content.get("current", {}) if isinstance(content, dict) else {}
            value = current.get("value") if isinstance(current, dict) else None
            metrics.append({
                "title": item.get("title", ""),
                "value": value,
            })
        if metrics:
            result["metrics"] = metrics
            if len(metrics) == 1:
                result["metric_title"] = metrics[0]["title"]
                result["metric_value"] = metrics[0]["value"]
        return result

    if not isinstance(data, dict):
        return result

    categories = data.get("categories_ms", data.get("categories", []))
    parsed_categories = [
        _ts_to_date(c) if isinstance(c, (int, float)) and c > 1e12 else str(c)
        for c in categories[:500]
    ]
    if parsed_categories:
        result["categories"] = parsed_categories

    graphs = data.get("graphs", [])
    if graphs:
        series = []
        for g in graphs:
            points = []
            for idx, pt in enumerate(g.get("data", [])):
                if isinstance(pt, dict) and "x" in pt and "y" in pt:
                    x_val = pt["x"]
                    point: dict[str, Any] = {"value": pt["y"]}
                    # QL-графики часто отдают x как индекс категории (0..N-1).
                    if (
                        isinstance(x_val, (int, float))
                        and parsed_categories
                        and float(x_val).is_integer()
                        and 0 <= int(x_val) < len(parsed_categories)
                    ):
                        point["category"] = parsed_categories[int(x_val)]
                    elif isinstance(x_val, (int, float)):
                        point["date"] = _ts_to_date(x_val)
                    points.append(point)
                elif isinstance(pt, dict) and "y" in pt:
                    point: dict[str, Any] = {"value": pt["y"]}
                    if idx < len(parsed_categories):
                        point["category"] = parsed_categories[idx]
                    points.append(point)
            series.append({
                "name": g.get("title", g.get("legendTitle", "")),
                "points_count": len(points),
                "points": points,
            })
        result["series"] = series
        result["series_count"] = len(series)
        return result

    # Таблицы: data.head + data.rows (или data.columns + data.rows)
    head = data.get("head", [])
    rows = data.get("rows", [])
    if head and rows:
        columns = [h.get("name", h.get("id", f"col_{i}")) for i, h in enumerate(head)]
        table_rows = []
        for row in rows[:500]:  # ограничиваем для разумного размера
            values: Any = row
            if isinstance(row, dict):
                if isinstance(row.get("values"), list):
                    values = row["values"]
                elif isinstance(row.get("cells"), list):
                    # table_wizard_node often returns rows as {"cells": [{"value": ...}, ...]}
                    values = [
                        cell.get("value") if isinstance(cell, dict) else cell
                        for cell in row["cells"]
                    ]
                else:
                    values = row
            if isinstance(values, list):
                table_rows.append(dict(zip(columns, values)))
        result["columns"] = columns
        result["rows"] = table_rows
        result["rows_count"] = len(rows)
        return result

    return result


def _iter_selectors(tab: dict) -> list[dict]:
    """Вернуть селекторы таба в том же формате, что и в analyze_dashboard."""
    selectors: list[dict] = []
    for item in tab.get("items", []):
        item_type = item.get("type")
        item_data = item.get("data", {})
        if item_type not in ("control", "group_control"):
            continue
        groups = item_data.get("group", [item_data])
        for g in groups:
            source = g.get("source", {})
            selectors.append({
                "title": g.get("title", ""),
                "field_name": source.get("fieldName", g.get("fieldName", "")),
                "default_value": g.get("defaults", source.get("defaultValue")),
            })
    return selectors


def get_tab_context_for_chart(dash_id: str, chart_id: str) -> dict:
    """Получить дефолтные параметры таба для конкретного чарта."""
    entry = get_dashboard(dash_id)
    if "error" in entry:
        return {"error": entry["error"], "dashboard_id": dash_id, "chart_id": chart_id}

    tabs = entry.get("data", {}).get("tabs", [])
    for tab in tabs:
        chart_found = False
        for item in tab.get("items", []):
            if item.get("type") != "widget":
                continue
            chart_tabs = item.get("data", {}).get("tabs", [])
            if not chart_tabs:
                continue
            if chart_tabs[0].get("chartId") == chart_id:
                chart_found = True
                break
        if not chart_found:
            continue

        params: dict[str, Any] = {}
        selectors = _iter_selectors(tab)
        for selector in selectors:
            defaults = selector.get("default_value")
            field_name = selector.get("field_name")
            if isinstance(defaults, dict):
                params.update(defaults)
            elif field_name and defaults not in (None, ""):
                params[field_name] = defaults

        # aliases: [["left", "right"], ...]
        aliases = tab.get("aliases", {}).get("default", [])
        if isinstance(aliases, list):
            for pair in aliases:
                if not isinstance(pair, list) or len(pair) != 2:
                    continue
                left, right = pair
                if left in params and right not in params:
                    params[right] = params[left]
                elif right in params and left not in params:
                    params[left] = params[right]

        return {
            "dashboard_id": dash_id,
            "tab_id": tab.get("id"),
            "tab_title": tab.get("title", ""),
            "chart_id": chart_id,
            "params": params,
            "selectors_count": len(selectors),
        }

    return {"error": "chart_not_found_in_dashboard", "dashboard_id": dash_id, "chart_id": chart_id}


def _extract_period_value(parsed: dict, period: str, aggregate: str) -> dict:
    """Извлечь значение за период из series[].points."""
    target_date = period
    if len(period) == 7:  # YYYY-MM
        target_date = f"{period}-01"

    rows = []
    for s in parsed.get("series", []):
        for p in s.get("points", []):
            value = p.get("value")
            if not isinstance(value, (int, float)):
                continue
            point_date = p.get("date")
            point_category = p.get("category")
            # 1) календарный матч (YYYY-MM-DD)
            if point_date == target_date:
                rows.append({"series": s.get("name", ""), "value": value})
                continue
            # 2) месячный матч по category (YYYY-MM)
            if len(period) == 7 and point_category == period:
                rows.append({"series": s.get("name", ""), "value": value})
                continue
            # 3) fallback: date начинается с YYYY-MM
            if len(period) == 7 and isinstance(point_date, str) and point_date.startswith(period):
                rows.append({"series": s.get("name", ""), "value": value})

    if not rows:
        return {
            "period": period,
            "target_date": target_date,
            "aggregate": aggregate,
            "value": None,
            "series_breakdown": [],
        }

    if aggregate == "series-first":
        value = rows[0]["value"]
    elif aggregate == "stack-sum" or (aggregate == "auto" and len(rows) > 1):
        value = sum(r["value"] for r in rows)
        aggregate = "stack-sum"
    else:
        value = rows[0]["value"]
        aggregate = "series-first"

    return {
        "period": period,
        "target_date": target_date,
        "aggregate": aggregate,
        "value": value,
        "series_breakdown": rows,
    }


def _confidence_level(mode: str, fallback_used: bool) -> str:
    """Оценка уверенности в результате."""
    if fallback_used:
        return "low"
    if mode == "tab_context":
        return "high"
    return "medium"


def _collect_dashboard_widgets(entry: dict) -> list[dict[str, str]]:
    """Собрать все виджеты-чарты из дашборда."""
    widgets: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    tabs = entry.get("data", {}).get("tabs", [])
    for tab in tabs:
        tab_id = tab.get("id", "")
        tab_title = tab.get("title", "")
        for item in tab.get("items", []):
            if item.get("type") != "widget":
                continue
            chart_tabs = item.get("data", {}).get("tabs", [])
            if not chart_tabs:
                continue
            chart_id = chart_tabs[0].get("chartId", "")
            chart_title = chart_tabs[0].get("title", "")
            if not chart_id:
                continue
            key = (tab_id, chart_id)
            if key in seen:
                continue
            seen.add(key)
            widgets.append({
                "tab_id": tab_id,
                "tab_title": tab_title,
                "chart_id": chart_id,
                "chart_title": chart_title,
            })
    return widgets


def _extract_field_strings(fields: dict) -> list[str]:
    """Извлечь названия/формулы полей в плоский список строк."""
    out: list[str] = []
    for section_items in fields.values():
        if not isinstance(section_items, list):
            continue
        for item in section_items:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            formula = item.get("formula")
            if isinstance(title, str) and title:
                out.append(title)
            if isinstance(formula, str) and formula:
                out.append(formula)
    return out


def _tokenize_query(query: str) -> list[str]:
    return [t for t in re.findall(r"[0-9a-zA-Zа-яА-Я_]+", query.lower()) if len(t) >= 2]


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.replace(" ", "").replace(",", ".")
        try:
            return float(normalized)
        except ValueError:
            return None
    return None


def _guess_value_column(columns: list[str], rows: list[dict], preferred: str | None = None) -> str | None:
    if preferred and preferred in columns:
        return preferred
    if not columns or not rows:
        return None

    priority_names = {"count", "uniques", "hits", "value", "users", "number"}
    for col in columns:
        lc = col.lower()
        words = set(re.findall(r"[0-9a-zа-я]+", lc))
        if words & priority_names:
            return col
        if any(substr in lc for substr in ("колич", "значен", "метрик")):
            return col

    best_col = None
    best_ratio = -1.0
    sample = rows[: min(50, len(rows))]
    for col in columns:
        numeric = 0
        for row in sample:
            if _to_float(row.get(col)) is not None:
                numeric += 1
        ratio = numeric / len(sample) if sample else 0.0
        if ratio > best_ratio:
            best_ratio = ratio
            best_col = col
    return best_col


def _guess_group_column(columns: list[str], value_col: str | None, preferred: str | None = None) -> str | None:
    if preferred and preferred in columns:
        return preferred
    if not columns:
        return None
    priority_names = ("countr", "стра", "geo", "domain", "park", "language", "язык")
    for col in columns:
        if col == value_col:
            continue
        lc = col.lower()
        if any(name in lc for name in priority_names):
            return col
    for col in columns:
        if col != value_col:
            return col
    return columns[0]


def _period_to_interval_param(period: str) -> str:
    """
    Нормализовать период в формат __interval_... .
    Поддержка:
      - already encoded: __interval_... / __between_...
      - YYYY-MM
      - YYYY-MM-DD
      - YYYY-MM-DD:YYYY-MM-DD
    """
    period = period.strip()
    if period.startswith("__interval_") or period.startswith("__between_"):
        return period
    if re.fullmatch(r"\d{4}-\d{2}", period):
        year, month = map(int, period.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        return (
            f"__interval_{year:04d}-{month:02d}-01T00:00:00.000Z_"
            f"{year:04d}-{month:02d}-{last_day:02d}T23:59:59.999Z"
        )
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", period):
        return f"__interval_{period}T00:00:00.000Z_{period}T23:59:59.999Z"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}[:/]\d{4}-\d{2}-\d{2}", period):
        start, end = period.replace("/", ":").split(":")
        return f"__interval_{start}T00:00:00.000Z_{end}T23:59:59.999Z"
    raise ValueError(
        "Неподдерживаемый формат периода. Используйте YYYY-MM, YYYY-MM-DD, "
        "YYYY-MM-DD:YYYY-MM-DD или __interval_..."
    )


def _detect_period_param_key(context_params: dict, used_params: dict) -> str | None:
    """Определить ключ параметра периода (предпочтение фактическому used_params)."""
    candidates: list[tuple[int, str]] = []

    def _scan(params: dict, bonus: int) -> None:
        for key in params:
            lk = key.lower()
            score = 0
            if "eventdate" in lk:
                score = 100
            elif "date_interval" in lk or "date_from" in lk:
                score = 90
            elif lk == "eventdate":
                score = 80
            elif lk == "date":
                score = 60
            elif "date" in lk:
                score = 50
            if score:
                if "_" in key:
                    score += 3
                if key == "EventDate":
                    score -= 2
                candidates.append((score + bonus, key))

    _scan(used_params, 10)
    _scan(context_params, 0)
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def find_charts(
    dash_id: str,
    query: str,
    tab_id: str = "",
    tab_title_contains: str = "",
    limit: int = 10,
) -> dict:
    """Найти релевантные чарты по запросу (без полного analyze_dashboard)."""
    entry = get_dashboard(dash_id)
    if "error" in entry:
        return {"error": entry["error"], "dashboard_id": dash_id}

    query_tokens = _tokenize_query(query)
    widgets = _collect_dashboard_widgets(entry)
    results: list[dict[str, Any]] = []
    tab_title_filter = tab_title_contains.lower().strip()

    for widget in widgets:
        if tab_id and widget["tab_id"] != tab_id:
            continue
        if tab_title_filter and tab_title_filter not in widget["tab_title"].lower():
            continue

        chart_id = widget["chart_id"]
        chart_resp = get_chart(chart_id)
        if "error" in chart_resp:
            continue

        chart_name = chart_resp.get("key", widget["chart_title"]).split("/")[-1]
        config = parse_chart_config(chart_resp)
        fields = extract_fields(config)
        filters = extract_filters(config)
        field_strings = _extract_field_strings(fields)
        filter_strings = [f"{f['field']} {f['operation']}" for f in filters]

        haystack = " ".join([
            widget["tab_title"],
            widget["chart_title"],
            chart_name,
            " ".join(field_strings),
            " ".join(filter_strings),
        ]).lower()
        chart_title_l = widget["chart_title"].lower()
        tab_title_l = widget["tab_title"].lower()
        chart_name_l = chart_name.lower()

        score = 0
        matched_tokens = []
        for token in query_tokens:
            token_score = 0
            if token in chart_title_l:
                token_score = max(token_score, 8)
            if token in chart_name_l:
                token_score = max(token_score, 6)
            if token in tab_title_l:
                token_score = max(token_score, 5)
            if token in haystack:
                token_score = max(token_score, 2)
            if token_score > 0:
                score += token_score
                matched_tokens.append(token)

        if query_tokens and score == 0:
            continue

        results.append({
            "chart_id": chart_id,
            "chart_title": widget["chart_title"],
            "chart_name": chart_name,
            "tab_id": widget["tab_id"],
            "tab_title": widget["tab_title"],
            "chart_type": chart_resp.get("_chart_type", ""),
            "visualization": parse_chart_config(chart_resp).get("visualization", {}).get("id", ""),
            "score": score if query_tokens else 0,
            "matched_tokens": sorted(set(matched_tokens)),
            "fields_preview": field_strings[:8],
        })

    results.sort(key=lambda x: (x.get("score", 0), x.get("tab_title", ""), x.get("chart_title", "")), reverse=True)
    if limit > 0:
        results = results[:limit]
    return {
        "dashboard_id": dash_id,
        "query": query,
        "query_tokens": query_tokens,
        "filters": {
            "tab_id": tab_id,
            "tab_title_contains": tab_title_contains,
            "limit": limit,
        },
        "results": results,
        "results_count": len(results),
    }


def run_topn(
    dash_id: str,
    chart_id: str,
    period: str | None = None,
    top_n: int = 3,
    count_by: str | None = None,
    group_column: str | None = None,
    value_column: str | None = None,
    period_key: str | None = None,
    user_params: dict[str, Any] | None = None,
) -> dict:
    """
    Выполнить табличный чарт и вернуть top-N строк по числовому столбцу.
    Ускоряет сценарий "найти топ стран/доменов/парков за период".
    """
    context = get_tab_context_for_chart(dash_id, chart_id)
    if "error" in context:
        return context

    final_params = dict(context.get("params", {}))
    if user_params:
        final_params |= user_params

    # Базовый запуск помогает понять реальные ключи used_params.
    probe_raw = run_chart(chart_id, final_params)
    if "error" in probe_raw:
        return {
            "error": probe_raw.get("error"),
            "message": probe_raw.get("message", ""),
            "dashboard_id": dash_id,
            "chart_id": chart_id,
            "phase": "probe",
        }
    probe_parsed = parse_chart_data(probe_raw)
    used_params = probe_parsed.get("used_params", {})

    resolved_period_key = period_key or _detect_period_param_key(final_params, used_params)
    resolved_period_expr = None
    if period:
        try:
            resolved_period_expr = _period_to_interval_param(period)
        except ValueError as e:
            return {"error": "invalid_period", "message": str(e), "period": period}
        if resolved_period_key:
            final_params[resolved_period_key] = [resolved_period_expr]

    if count_by:
        final_params["count_by"] = [count_by]

    raw = run_chart(chart_id, final_params)
    if "error" in raw and resolved_period_key and resolved_period_expr is not None:
        # Fallback: иногда backend ожидает скаляр вместо массива.
        alt_params = dict(final_params)
        alt_params[resolved_period_key] = resolved_period_expr
        raw = run_chart(chart_id, alt_params)
        if "error" not in raw:
            final_params = alt_params

    if "error" in raw:
        return {
            "error": raw.get("error"),
            "message": raw.get("message", ""),
            "dashboard_id": dash_id,
            "chart_id": chart_id,
            "tab_context": context,
            "params": final_params,
        }

    parsed = parse_chart_data(raw)
    rows = parsed.get("rows", [])
    columns = parsed.get("columns", [])
    if not rows or not columns:
        return {
            "error": "chart_has_no_table_rows",
            "dashboard_id": dash_id,
            "chart_id": chart_id,
            "tab_context": context,
            "parsed": parsed,
        }

    resolved_value_column = _guess_value_column(columns, rows, value_column)
    resolved_group_column = _guess_group_column(columns, resolved_value_column, group_column)
    if not resolved_value_column or not resolved_group_column:
        return {
            "error": "cannot_resolve_columns",
            "columns": columns,
            "requested": {"group_column": group_column, "value_column": value_column},
        }

    sortable: list[dict[str, Any]] = []
    for row in rows:
        numeric_value = _to_float(row.get(resolved_value_column))
        if numeric_value is None:
            continue
        sortable.append({
            "group": row.get(resolved_group_column),
            "value": numeric_value,
            "row": row,
        })
    sortable.sort(key=lambda x: x["value"], reverse=True)
    top_rows = sortable[: max(top_n, 1)]

    result: dict[str, Any] = {
        "dashboard_id": dash_id,
        "chart_id": chart_id,
        "tab_context": {
            "tab_id": context.get("tab_id"),
            "tab_title": context.get("tab_title"),
        },
        "period": period,
        "period_expr": resolved_period_expr,
        "period_key": resolved_period_key,
        "count_by": count_by,
        "resolved_columns": {
            "group_column": resolved_group_column,
            "value_column": resolved_value_column,
        },
        "top_n": top_n,
        "top": top_rows,
        "used_params": parsed.get("used_params", {}),
        "rows_count": parsed.get("rows_count", len(rows)),
    }
    result["confidence"] = _confidence_level("tab_context", False)
    return result


def probe_selector_values(
    dash_id: str,
    chart_id: str,
    selector_key: str,
    candidates: list[str],
    period: str | None = None,
    period_key: str | None = None,
    user_params: dict[str, Any] | None = None,
) -> dict:
    """
    Пробует набор значений селектора и показывает, какие значения реально применились.
    Полезно для count_by, когда UI значение неочевидно.
    """
    context = get_tab_context_for_chart(dash_id, chart_id)
    if "error" in context:
        return context

    base_params = dict(context.get("params", {}))
    if user_params:
        base_params |= user_params

    warmup_raw = run_chart(chart_id, base_params)
    warmup_used = {}
    if "error" not in warmup_raw:
        warmup_used = warmup_raw.get("usedParams", warmup_raw.get("params", {}))

    resolved_period_key = period_key or _detect_period_param_key(base_params, warmup_used)
    if period:
        period_expr = _period_to_interval_param(period)
        if resolved_period_key:
            base_params[resolved_period_key] = [period_expr]

    attempts = []
    for value in candidates:
        params = dict(base_params)
        params[selector_key] = [value]
        raw = run_chart(chart_id, params)
        if "error" in raw:
            attempts.append({
                "value": value,
                "status": "error",
                "error": raw.get("error"),
                "message": raw.get("message", ""),
            })
            continue
        parsed = parse_chart_data(raw)
        first_row = parsed.get("rows", [{}])[0] if parsed.get("rows") else {}
        first_series_point = None
        if parsed.get("series"):
            points = parsed["series"][0].get("points", [])
            if points:
                first_series_point = points[0]
        attempts.append({
            "value": value,
            "status": "ok",
            "applied_value": parsed.get("used_params", {}).get(selector_key),
            "rows_count": parsed.get("rows_count"),
            "first_row": first_row,
            "first_series_point": first_series_point,
        })

    return {
        "dashboard_id": dash_id,
        "chart_id": chart_id,
        "selector_key": selector_key,
        "period": period,
        "period_key": resolved_period_key,
        "attempts": attempts,
        "ok_values": [a["value"] for a in attempts if a.get("status") == "ok"],
    }


def list_charts(dash_id: str) -> list[dict]:
    """Получить список чартов дашборда (только id + title, без деталей)."""
    entry = get_dashboard(dash_id)
    if "error" in entry:
        return [{"error": entry["error"]}]

    charts = []
    seen: set[str] = set()
    for w in _collect_dashboard_widgets(entry):
        chart_id = w["chart_id"]
        if chart_id in seen:
            continue
        seen.add(chart_id)
        charts.append({
            "id": chart_id,
            "title": w["chart_title"],
            "tab": w["tab_title"],
            "tab_id": w["tab_id"],
        })
    return charts


def parse_chart_config(chart_response: dict) -> dict:
    """Извлечь конфигурацию из ответа getWizardChart/getQLChart/getEditorChart."""
    data = chart_response.get("data", {})
    chart_type = chart_response.get("_chart_type", "")

    # Editor-чарты: JS-код в data.graph, нет стандартной конфигурации
    if chart_type == "Editor" or chart_response.get("type") == "graph_node":
        return {"_editor": True, "type": chart_response.get("type", "editor")}

    shared_raw = data.get("shared")
    if isinstance(shared_raw, str):
        try:
            return json.loads(shared_raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    if isinstance(shared_raw, dict):
        return shared_raw
    return data


def _parse_placeholders(placeholders: list) -> dict:
    """Извлечь поля из списка placeholders."""
    fields = {}
    for ph in placeholders:
        if not isinstance(ph, dict):
            continue
        section = ph.get("id", "unknown")
        items = []
        for f in ph.get("items", []):
            item = {
                "title": f.get("title"),
                "guid": f.get("guid"),
                "data_type": f.get("data_type"),
                "aggregation": f.get("aggregation", "none"),
            }
            if f.get("formula"):
                item["formula"] = f["formula"]
            items.append(item)
        if items:
            fields[section] = items
    return fields


def extract_fields(chart_config: dict) -> dict:
    """Извлечь поля из placeholders чарта (включая combined-chart layers)."""
    if chart_config.get("_editor"):
        return {}

    viz = chart_config.get("visualization", {})

    # combined-chart: поля внутри layers[].placeholders[]
    layers = viz.get("layers", [])
    if layers:
        fields: dict[str, Any] = {}
        for i, layer in enumerate(layers):
            layer_fields = _parse_placeholders(layer.get("placeholders", []))
            layer_type = layer.get("type", layer.get("id", f"layer_{i}"))
            if layer_fields:
                if len(layers) > 1:
                    for section, items in layer_fields.items():
                        key = f"{section} ({layer_type})" if section in fields else section
                        fields[key] = items
                else:
                    fields.update(layer_fields)
        return fields

    # Обычные чарты: visualization.placeholders[]
    return _parse_placeholders(viz.get("placeholders", []))


def extract_filters(chart_config: dict) -> list:
    """Извлечь фильтры чарта."""
    filters = []
    for f in chart_config.get("filters", []):
        flt = f.get("filter", {})
        filters.append({
            "field": f.get("title", f.get("datasetFieldId", "?")),
            "operation": flt.get("operation", {}).get("code", "unknown"),
            "values": flt.get("value", []),
        })
    return filters


def parse_dataset(ds_response: dict) -> dict:
    """Разобрать датасет из ответа getDataset."""
    ds_data = ds_response.get("dataset", {})
    schema = ds_data.get("result_schema", [])

    fields = []
    formulas = []
    for f in schema:
        info = {
            "title": f.get("title"),
            "guid": f.get("guid"),
            "data_type": f.get("data_type"),
            "aggregation": f.get("aggregation", "none"),
            "calc_mode": f.get("calc_mode"),
            "source": f.get("source", ""),
        }
        if f.get("calc_mode") == "formula":
            info["formula"] = f.get("formula", "")
            formulas.append({"title": f.get("title"), "formula": f.get("formula")})
        fields.append(info)

    sources = []
    for src in ds_data.get("sources", []):
        sources.append({
            "title": src.get("title"),
            "connection_id": src.get("connection_id"),
            "source_type": src.get("source_type"),
            "parameters": {
                k: v for k, v in src.get("parameters", {}).items()
                if k in ("table_name", "db_name", "schema_name", "sub_source", "subsql")
            },
        })

    return {
        "name": ds_response.get("key", "").split("/")[-1],
        "id": ds_response.get("id"),
        "fields_count": len(fields),
        "formulas_count": len(formulas),
        "fields": fields,
        "formulas": formulas,
        "sources": sources,
    }


def analyze_dashboard(dash_id: str) -> dict:
    """Полный анализ дашборда."""
    print(f"[1/5] Получаю дашборд {dash_id}...", file=sys.stderr)
    entry = get_dashboard(dash_id)

    if "error" in entry:
        return {"error": entry["error"], "dashboard_id": dash_id}

    data = entry.get("data", {})
    tabs = data.get("tabs", [])

    report: dict[str, Any] = {
        "dashboard": {
            "id": entry.get("entryId"),
            "key": entry.get("key"),
            "scope": entry.get("scope"),
            "created_at": entry.get("createdAt"),
            "updated_at": entry.get("updatedAt"),
            "tabs_count": len(tabs),
            "annotation": (entry.get("annotation") or {}).get("description", ""),
        },
        "tabs": [],
        "datasets": {},
        "connections": {},
        "summary": {
            "total_charts": 0,
            "total_selectors": 0,
            "total_datasets": 0,
            "chart_types": {},
        },
    }

    seen_charts: set[str] = set()

    for i, tab in enumerate(tabs):
        print(f"[2/5] Обрабатываю таб {i+1}/{len(tabs)}: {tab.get('title', '?')}",
              file=sys.stderr)

        tab_info: dict[str, Any] = {
            "title": tab.get("title", "Без названия"),
            "id": tab.get("id"),
            "charts": [],
            "selectors": [],
            "texts": [],
        }

        items = tab.get("items", [])
        for item in items:
            item_type = item.get("type")
            item_data = item.get("data", {})

            if item_type == "widget":
                chart_tabs = item_data.get("tabs", [])
                chart_id = chart_tabs[0].get("chartId") if chart_tabs else None
                chart_title = chart_tabs[0].get("title", "") if chart_tabs else ""
                if not chart_id:
                    continue

                if chart_id in seen_charts:
                    tab_info["charts"].append({
                        "id": chart_id,
                        "name": chart_title,
                        "note": "дубликат (уже обработан выше)",
                    })
                    report["summary"]["total_charts"] += 1
                    continue
                seen_charts.add(chart_id)

                print(f"  [3/5] Получаю чарт {chart_id}...", file=sys.stderr)
                try:
                    chart_response = get_chart(chart_id)
                    if "error" in chart_response:
                        tab_info["charts"].append({
                            "id": chart_id, "name": chart_title,
                            "error": chart_response["error"],
                        })
                        continue

                    config = parse_chart_config(chart_response)
                    if config.get("_editor"):
                        vis_type = "editor"
                    else:
                        viz = config.get("visualization", {})
                        vis_type = viz.get("id", config.get("type", "unknown"))

                    report["summary"]["chart_types"][vis_type] = (
                        report["summary"]["chart_types"].get(vis_type, 0) + 1
                    )
                    report["summary"]["total_charts"] += 1

                    dataset_ids = config.get("datasetsIds", [])
                    ds_id = dataset_ids[0] if dataset_ids else ""

                    chart_info: dict[str, Any] = {
                        "id": chart_id,
                        "name": chart_response.get("key", chart_title).split("/")[-1],
                        "chart_type": chart_response.get("_chart_type", "Wizard"),
                        "visualization": vis_type,
                        "dataset_id": ds_id,
                        "fields": extract_fields(config),
                        "filters": extract_filters(config),
                    }

                    tab_info["charts"].append(chart_info)

                    for did in dataset_ids:
                        if did and did not in report["datasets"]:
                            print(f"  [4/5] Получаю датасет {did}...", file=sys.stderr)
                            try:
                                ds_response = get_dataset(did)
                                if "error" not in ds_response:
                                    parsed = parse_dataset(ds_response)
                                    report["datasets"][did] = parsed

                                    for src in parsed.get("sources", []):
                                        conn_id = src.get("connection_id")
                                        if conn_id and conn_id not in report["connections"]:
                                            print(f"  [5/5] Получаю подключение {conn_id}...",
                                                  file=sys.stderr)
                                            try:
                                                conn = get_connection(conn_id)
                                                if "error" not in conn:
                                                    report["connections"][conn_id] = {
                                                        "name": conn.get("key", "").split("/")[-1],
                                                        "type": conn.get("data", {}).get("type"),
                                                    }
                                            except Exception:
                                                pass
                                else:
                                    report["datasets"][did] = {"error": ds_response["error"]}
                            except Exception:
                                report["datasets"][did] = {"error": "no_access"}

                except Exception as e:
                    tab_info["charts"].append({
                        "id": chart_id, "name": chart_title, "error": str(e),
                    })

            elif item_type in ("control", "group_control"):
                groups = item_data.get("group", [item_data])
                for g in groups:
                    report["summary"]["total_selectors"] += 1
                    source = g.get("source", {})
                    tab_info["selectors"].append({
                        "title": g.get("title", ""),
                        "source_type": g.get("sourceType", "manual"),
                        "field_name": source.get("fieldName", g.get("fieldName", "")),
                        "element_type": source.get("elementType", ""),
                        "default_value": g.get("defaults", source.get("defaultValue")),
                    })

            elif item_type in ("text", "title"):
                tab_info["texts"].append({
                    "type": item_type,
                    "content": str(item_data.get("text", ""))[:300],
                })

        tab_info["widget_connections"] = tab.get("connections", [])
        tab_info["aliases"] = tab.get("aliases", {})
        report["tabs"].append(tab_info)

    report["summary"]["total_datasets"] = len(report["datasets"])
    print("Готово!", file=sys.stderr)
    return report


def main():
    parser = argparse.ArgumentParser(description="DataLens Dashboard Analyzer")
    parser.add_argument("dashboard_id", nargs="?", help="ID дашборда DataLens")
    parser.add_argument("--output", "-o", help="Сохранить отчёт в файл (JSON)")
    parser.add_argument("--list-charts", action="store_true",
                        help="Вывести список чартов дашборда (быстро)")
    parser.add_argument("--inspect-chart", metavar="CHART_ID",
                        help="Показать метаданные чарта: SQL, connection, placeholders, colors")
    parser.add_argument("--run-chart", metavar="CHART_ID",
                        help="Выполнить чарт и получить данные")
    parser.add_argument("--run-chart-with-tab-context", nargs=2, metavar=("DASHBOARD_ID", "CHART_ID"),
                        help="Выполнить чарт с дефолтными селекторами таба")
    parser.add_argument("--run-topn", nargs=2, metavar=("DASHBOARD_ID", "CHART_ID"),
                        help="Выполнить табличный чарт с контекстом таба и вернуть top-N")
    parser.add_argument("--top-n", type=int, default=3,
                        help="Размер top-N для --run-topn (по умолчанию: 3)")
    parser.add_argument("--period",
                        help="Период для --run-topn/--probe-selector-values: YYYY-MM | "
                             "YYYY-MM-DD | YYYY-MM-DD:YYYY-MM-DD | __interval_...")
    parser.add_argument("--period-key",
                        help="Явный ключ параметра периода (если автоопределение не подходит)")
    parser.add_argument("--count-by",
                        help="Значение селектора count_by (например: hits, uniques)")
    parser.add_argument("--group-column",
                        help="Явное имя группирующего столбца для --run-topn")
    parser.add_argument("--value-column",
                        help="Явное имя числового столбца для --run-topn")
    parser.add_argument("--find-chart", metavar="QUERY",
                        help="Найти релевантные чарты по запросу")
    parser.add_argument("--find-tab-id", default="",
                        help="Фильтр для --find-chart по id таба")
    parser.add_argument("--find-tab-title", default="",
                        help="Фильтр для --find-chart по части названия таба")
    parser.add_argument("--find-limit", type=int, default=10,
                        help="Лимит результатов для --find-chart")
    parser.add_argument("--probe-selector-values", nargs=3, metavar=("DASHBOARD_ID", "CHART_ID", "SELECTOR_KEY"),
                        help="Пробовать набор значений селектора и показать применившиеся")
    parser.add_argument("--probe-candidates",
                        help="JSON-массив кандидатов для --probe-selector-values")
    parser.add_argument("--params", default="{}",
                        help="JSON с параметрами для --run-chart")
    parser.add_argument("--fallback-chart", metavar="CHART_ID",
                        help="Fallback-чарт, если основной вернёт ошибку")
    parser.add_argument("--value-at-period",
                        help="Период для извлечения значения: YYYY-MM или YYYY-MM-DD")
    parser.add_argument("--aggregate", choices=["auto", "stack-sum", "series-first"], default="auto",
                        help="Как агрегировать значение периода")
    parser.add_argument("--token-file",
                        help="Путь к файлу с OAuth-токеном (альтернатива DATALENS_OAUTH_TOKEN)")
    args = parser.parse_args()

    # Переопределяем токен из --token-file, если указан
    global TOKEN, HEADERS
    if args.token_file:
        TOKEN = _parse_token_file(args.token_file)
        HEADERS["Authorization"] = f"OAuth {TOKEN}"

    if not TOKEN:
        print("ОШИБКА: задайте DATALENS_OAUTH_TOKEN", file=sys.stderr)
        sys.exit(1)

    try:
        user_params = json.loads(args.params)
        if not isinstance(user_params, dict):
            raise ValueError("params must be object")
    except Exception:
        print("ОШИБКА: --params должен быть JSON-объектом", file=sys.stderr)
        sys.exit(1)

    probe_candidates = ["hits", "uniques", "users", "users_count", "unique"]
    if args.probe_candidates:
        try:
            loaded = json.loads(args.probe_candidates)
            if not isinstance(loaded, list) or not all(isinstance(x, str) for x in loaded):
                raise ValueError("probe candidates must be list[str]")
            probe_candidates = loaded
        except Exception:
            print("ОШИБКА: --probe-candidates должен быть JSON-массивом строк", file=sys.stderr)
            sys.exit(1)

    mode = "default"
    fallback_used = False
    if args.run_topn:
        dash_id, chart_id = args.run_topn
        mode = "tab_context"
        print(f"Выполняю top-{args.top_n} по чарту {chart_id}...", file=sys.stderr)
        result = run_topn(
            dash_id=dash_id,
            chart_id=chart_id,
            period=args.period,
            top_n=args.top_n,
            count_by=args.count_by,
            group_column=args.group_column,
            value_column=args.value_column,
            period_key=args.period_key,
            user_params=user_params,
        )
    elif args.probe_selector_values:
        dash_id, chart_id, selector_key = args.probe_selector_values
        mode = "tab_context"
        print(f"Пробую значения селектора {selector_key} для чарта {chart_id}...", file=sys.stderr)
        result = probe_selector_values(
            dash_id=dash_id,
            chart_id=chart_id,
            selector_key=selector_key,
            candidates=probe_candidates,
            period=args.period,
            period_key=args.period_key,
            user_params=user_params,
        )
    elif args.inspect_chart:
        result = inspect_chart(args.inspect_chart)
    elif args.find_chart:
        if not args.dashboard_id:
            print("ОШИБКА: для --find-chart укажите dashboard_id", file=sys.stderr)
            sys.exit(1)
        print(f"Ищу релевантные чарты: '{args.find_chart}'...", file=sys.stderr)
        result = find_charts(
            dash_id=args.dashboard_id,
            query=args.find_chart,
            tab_id=args.find_tab_id,
            tab_title_contains=args.find_tab_title,
            limit=args.find_limit,
        )
    elif args.run_chart_with_tab_context:
        dash_id, chart_id = args.run_chart_with_tab_context
        context = get_tab_context_for_chart(dash_id, chart_id)
        if "error" in context:
            result = context
        else:
            mode = "tab_context"
            print(f"Выполняю чарт {chart_id} с контекстом таба '{context['tab_title']}'...", file=sys.stderr)
            final_params = context["params"] | user_params
            raw = run_chart(chart_id, final_params)
            if "error" in raw and args.fallback_chart:
                fallback_used = True
                raw = run_chart(args.fallback_chart, final_params)
                if "error" in raw:
                    result = {
                        "error": raw.get("error"),
                        "message": raw.get("message", ""),
                        "fallback_used": True,
                        "primary_chart_id": chart_id,
                        "fallback_chart_id": args.fallback_chart,
                    }
                else:
                    result = parse_chart_data(raw)
                    result["fallback_used"] = True
                    result["primary_chart_id"] = chart_id
                    result["fallback_chart_id"] = args.fallback_chart
            elif "error" in raw:
                result = raw
            else:
                result = parse_chart_data(raw)
            if "error" not in result:
                result["tab_context"] = context
    elif args.run_chart:
        print(f"Выполняю чарт {args.run_chart}...", file=sys.stderr)
        raw = run_chart(args.run_chart, user_params)
        if "error" in raw and args.fallback_chart:
            fallback_used = True
            raw = run_chart(args.fallback_chart, user_params)
            if "error" in raw:
                result = {
                    "error": raw.get("error"),
                    "message": raw.get("message", ""),
                    "fallback_used": True,
                    "primary_chart_id": args.run_chart,
                    "fallback_chart_id": args.fallback_chart,
                }
            else:
                result = parse_chart_data(raw)
                result["fallback_used"] = True
                result["primary_chart_id"] = args.run_chart
                result["fallback_chart_id"] = args.fallback_chart
        elif "error" in raw:
            result = raw
        else:
            result = parse_chart_data(raw)
    elif args.list_charts:
        if not args.dashboard_id:
            print("ОШИБКА: укажите dashboard_id", file=sys.stderr)
            sys.exit(1)
        result = list_charts(args.dashboard_id)
    else:
        if not args.dashboard_id:
            print("ОШИБКА: укажите dashboard_id или --run-chart", file=sys.stderr)
            sys.exit(1)
        result = analyze_dashboard(args.dashboard_id)

    if isinstance(result, dict) and "error" not in result:
        if args.value_at_period:
            result["period_value"] = _extract_period_value(result, args.value_at_period, args.aggregate)
        if "confidence" not in result:
            result["confidence"] = _confidence_level(mode, fallback_used or bool(result.get("fallback_used")))

    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Отчёт сохранён: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
