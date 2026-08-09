#!/usr/bin/env python3
"""
DataLens chart creation/edit helpers.

Поддерживает:
- ad-hoc SQL через dashsql connection;
- createQLChart из существующего QL-чарта;
- добавление existing chart в dashboard;
- короткий путь: создать чарт и сразу прикрепить к dashboard.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import urllib.error
import urllib.request
from typing import Any

import analyze as dl


DASHSQL_HOST = os.environ.get("DATALENS_DASHSQL_HOST", "https://back.datalens.yandex-team.ru")
DEFAULT_GRID_WIDTH = 30


def _set_token_from_file(token_file: str) -> None:
    dl.TOKEN = dl._parse_token_file(token_file)
    dl.HEADERS["Authorization"] = f"OAuth {dl.TOKEN}"


def _assert_token() -> None:
    if not dl.TOKEN:
        raise SystemExit("ОШИБКА: задайте DATALENS_OAUTH_TOKEN")


def _parse_json_object(raw: str, flag_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(f"ОШИБКА: {flag_name} должен быть JSON-объектом: {e}") from e
    if not isinstance(parsed, dict):
        raise SystemExit(f"ОШИБКА: {flag_name} должен быть JSON-объектом")
    return parsed


def run_dashsql(
    connection_id: str,
    sql_query: str,
    params: dict[str, Any] | None = None,
    timeout_sec: float = 20.0,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"OAuth {dl.TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = json.dumps({"sql_query": sql_query, "params": params or {}}).encode("utf-8")
    req = urllib.request.Request(
        f"{DASHSQL_HOST}/api/data/v1/connections/{connection_id}/dashsql",
        data=body,
        method="POST",
    )
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, context=dl._SSL_CTX, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
        data = json.loads(e.read().decode("utf-8"))
    except Exception as e:
        return {
            "error": "dashsql_timeout_or_network_error",
            "message": str(e),
            "connection_id": connection_id,
            "timeout_sec": timeout_sec,
        }
    if status >= 400:
        return {
            "error": data.get("code", f"http_{status}"),
            "message": data.get("message", ""),
            "details": data.get("details", {}),
            "connection_id": connection_id,
        }
    return data


def _ensure_ql_chart(chart: dict, chart_id: str) -> None:
    if "error" in chart:
        raise SystemExit(f"ОШИБКА: не удалось получить source chart {chart_id}: {chart['error']}")
    if chart.get("data", {}).get("type") != "ql":
        raise SystemExit("ОШИБКА: source chart должен быть QL-чартом")


def _set_placeholder_item(data: dict, placeholder_id: str, guid: str | None, title: str | None) -> None:
    if not guid and not title:
        return
    for placeholder in data.get("visualization", {}).get("placeholders", []):
        if placeholder.get("id") != placeholder_id:
            continue
        items = placeholder.get("items", [])
        if not items:
            return
        if guid:
            items[0]["guid"] = guid
        if title:
            items[0]["title"] = title
        return


def _set_color_item(data: dict, guid: str | None, title: str | None) -> None:
    """Установить color dimension для QL-чарта (stacked/grouped визуализация)."""
    if not guid and not title:
        return
    data["colors"] = [{
        "guid": guid or title,
        "title": title or guid,
        "datasetId": "ql-mocked-dataset",
        "data_type": "string",
        "cast": "string",
        "type": "DIMENSION",
        "calc_mode": "direct",
        "inspectHidden": True,
        "formulaHidden": True,
        "noEdit": True,
    }]


def _summarize_run(run_response: dict) -> dict[str, Any]:
    parsed = dl.parse_chart_data(run_response)
    summary: dict[str, Any] = {
        "chart_id": parsed.get("chart_id"),
        "chart_name": parsed.get("chart_name"),
        "chart_type": parsed.get("chart_type"),
        "used_params": parsed.get("used_params", {}),
    }
    if parsed.get("series"):
        summary["series_count"] = parsed.get("series_count", 0)
        summary["points_count"] = parsed["series"][0].get("points_count", 0)
        summary["sample_points"] = parsed["series"][0].get("points", [])[:5]
    if parsed.get("rows"):
        summary["rows_count"] = parsed.get("rows_count", len(parsed["rows"]))
        summary["sample_rows"] = parsed["rows"][:5]
    if parsed.get("metrics"):
        summary["metrics"] = parsed["metrics"]
    return summary


def clone_ql_chart(
    source_chart_id: str,
    chart_key: str,
    sql_query: str,
    description: str = "",
    x_guid: str | None = None,
    x_title: str | None = None,
    y_guid: str | None = None,
    y_title: str | None = None,
    color_guid: str | None = None,
    color_title: str | None = None,
    validate: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    source_chart = dl.get_chart(source_chart_id)
    _ensure_ql_chart(source_chart, source_chart_id)

    chart_data = copy.deepcopy(source_chart["data"])
    chart_data["queryValue"] = sql_query
    _set_placeholder_item(chart_data, "x", x_guid, x_title)
    _set_placeholder_item(chart_data, "y", y_guid, y_title)
    _set_color_item(chart_data, color_guid, color_title)

    payload = {
        "template": "ql",
        "key": chart_key,
        "data": chart_data,
        "meta": source_chart.get("meta", {}),
        "annotation": {"description": description},
        "hidden": False,
        "public": False,
    }
    if dry_run:
        return {"dry_run": True, "create_payload": payload, "source_chart_id": source_chart_id}

    created = dl._rpc("createQLChart", payload)
    if "error" in created:
        return created

    result: dict[str, Any] = {
        "source_chart_id": source_chart_id,
        "chart_id": created.get("entryId"),
        "chart_key": created.get("key", chart_key),
    }
    if validate:
        run_result = dl.run_chart(result["chart_id"], {})
        result["validation"] = run_result if "error" in run_result else _summarize_run(run_result)
    return result


def _find_tab(dashboard: dict, tab_id: str) -> dict:
    tabs = dashboard.get("data", {}).get("tabs", [])
    if not tabs:
        raise SystemExit("ОШИБКА: dashboard не содержит tabs")
    if not tab_id:
        return tabs[0]
    for tab in tabs:
        if tab.get("id") == tab_id:
            return tab
    raise SystemExit(f"ОШИБКА: tab_id {tab_id} не найден")


def _chart_id_by_widget(item: dict) -> str:
    tabs = item.get("data", {}).get("tabs", [])
    return tabs[0].get("chartId", "") if tabs else ""


def _layout_map(tab: dict) -> dict[str, dict[str, Any]]:
    return {item.get("i"): item for item in tab.get("layout", []) if item.get("i")}


def _next_free_id(existing_ids: set[str], prefix: str) -> str:
    n = 1
    while True:
        candidate = f"{prefix}{n}"
        if candidate not in existing_ids:
            return candidate
        n += 1


def _find_anchor_layout(tab: dict, anchor_chart_id: str) -> dict[str, Any] | None:
    if not anchor_chart_id:
        return None
    layout_by_id = _layout_map(tab)
    for item in tab.get("items", []):
        if _chart_id_by_widget(item) == anchor_chart_id:
            return layout_by_id.get(item.get("id"))
    return None


def _position_for_widget(
    tab: dict,
    position: str,
    width: int,
    anchor_chart_id: str,
    grid_width: int,
) -> tuple[int, int]:
    layout = tab.get("layout", [])
    if not layout:
        return 0, 0
    max_y = max((item.get("y", 0) + item.get("h", 0) for item in layout), default=0)
    anchor = _find_anchor_layout(tab, anchor_chart_id)
    if position == "end" or anchor is None:
        return 0, max_y
    if position == "below":
        return anchor.get("x", 0), anchor.get("y", 0) + anchor.get("h", 0)
    x = anchor.get("x", 0) + anchor.get("w", 0)
    y = anchor.get("y", 0)
    return (x, y) if x + width <= grid_width else (0, max_y)


def _update_dashboard(entry: dict, publish: bool = True) -> dict[str, Any]:
    """Обновить дашборд с понятной обработкой ошибки блокировки."""
    updated = dl._rpc(
        "updateDashboard",
        {
            "mode": "publish" if publish else "save",
            "entry": {
                "entryId": entry["entryId"],
                "data": entry["data"],
                "meta": entry.get("meta") or {},
            },
        },
    )
    if "error" in updated:
        err = updated.get("error", "")
        if "LOCKED" in str(err).upper():
            return {
                "error": "dashboard_locked",
                "message": "Дашборд заблокирован (открыт в режиме редактирования в браузере). "
                           "Закройте редактор и повторите.",
                "dashboard_id": entry.get("entryId", ""),
            }
        return updated
    return updated


def add_chart_to_dashboard(
    dashboard_id: str,
    chart_id: str,
    widget_title: str,
    tab_id: str = "",
    position: str = "right",
    anchor_chart_id: str = "",
    width: int = 15,
    height: int = 14,
    hide_title: bool = False,
    publish: bool = True,
    grid_width: int = DEFAULT_GRID_WIDTH,
    dry_run: bool = False,
) -> dict[str, Any]:
    dashboard = dl.get_dashboard(dashboard_id)
    if "error" in dashboard:
        return dashboard

    tab = _find_tab(dashboard, tab_id)
    for item in tab.get("items", []):
        if _chart_id_by_widget(item) == chart_id:
            return {"status": "already_present", "dashboard_id": dashboard_id, "chart_id": chart_id}

    existing_item_ids = {item.get("id", "") for item in tab.get("items", [])}
    existing_tab_ids = {
        widget_tab.get("id", "")
        for item in tab.get("items", [])
        for widget_tab in item.get("data", {}).get("tabs", [])
    }
    widget_id = _next_free_id(existing_item_ids, "widget_")
    widget_tab_id = _next_free_id(existing_tab_ids, "tab_")
    x, y = _position_for_widget(tab, position, width, anchor_chart_id, grid_width)

    widget = {
        "id": widget_id,
        "data": {
            "tabs": [{
                "id": widget_tab_id,
                "hint": "",
                "title": widget_title,
                "params": {},
                "chartId": chart_id,
                "isDefault": True,
                "autoHeight": False,
                "background": {"color": "like-chart-bg"},
                "enableHint": False,
                "description": "",
                "enableDescription": False,
            }],
            "hideTitle": hide_title,
        },
        "type": "widget",
        "namespace": "default",
    }
    layout_item = {"h": height, "i": widget_id, "w": width, "x": x, "y": y}
    if dry_run:
        return {"dry_run": True, "widget": widget, "layout_item": layout_item}

    entry = copy.deepcopy(dashboard)
    target_tab = _find_tab(entry, tab.get("id"))
    target_tab["items"].append(widget)
    target_tab["layout"].append(layout_item)
    counter = entry.get("data", {}).get("counter", 0)
    entry["data"]["counter"] = max(counter + 1, len(target_tab["items"]) + 1)

    updated = _update_dashboard(entry, publish)
    if "error" in updated:
        return updated
    updated_entry = updated.get("entry", {})
    return {
        "dashboard_id": dashboard_id,
        "chart_id": chart_id,
        "tab_id": target_tab.get("id"),
        "widget_id": widget_id,
        "widget_title": widget_title,
        "layout": layout_item,
        "saved_id": updated_entry.get("savedId"),
        "published_id": updated_entry.get("publishedId"),
        "mode": "publish" if publish else "save",
    }


def replace_chart_on_dashboard(
    dashboard_id: str,
    old_chart_id: str,
    new_chart_id: str,
    widget_title: str | None = None,
    tab_id: str = "",
    publish: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Заменить чарт в существующем виджете дашборда."""
    dashboard = dl.get_dashboard(dashboard_id)
    if "error" in dashboard:
        return dashboard

    tab = _find_tab(dashboard, tab_id)
    found_item = None
    for item in tab.get("items", []):
        if _chart_id_by_widget(item) == old_chart_id:
            found_item = item
            break

    if not found_item:
        return {"error": "chart_not_found_in_dashboard",
                "old_chart_id": old_chart_id, "dashboard_id": dashboard_id}

    widget_tabs = found_item.get("data", {}).get("tabs", [])
    if widget_tabs:
        widget_tabs[0]["chartId"] = new_chart_id
        if widget_title is not None:
            widget_tabs[0]["title"] = widget_title

    if dry_run:
        return {"dry_run": True, "widget_id": found_item.get("id"),
                "old_chart_id": old_chart_id, "new_chart_id": new_chart_id,
                "widget": found_item}

    entry = copy.deepcopy(dashboard)
    target_tab = _find_tab(entry, tab.get("id"))
    for item in target_tab.get("items", []):
        if item.get("id") == found_item.get("id"):
            tabs = item.get("data", {}).get("tabs", [])
            if tabs:
                tabs[0]["chartId"] = new_chart_id
                if widget_title is not None:
                    tabs[0]["title"] = widget_title
            break

    updated = _update_dashboard(entry, publish)
    if "error" in updated:
        return updated
    updated_entry = updated.get("entry", {})
    return {
        "dashboard_id": dashboard_id,
        "old_chart_id": old_chart_id,
        "new_chart_id": new_chart_id,
        "widget_id": found_item.get("id"),
        "saved_id": updated_entry.get("savedId"),
        "published_id": updated_entry.get("publishedId"),
        "mode": "publish" if publish else "save",
    }


def clone_ql_to_dashboard(args: argparse.Namespace) -> dict[str, Any]:
    created = clone_ql_chart(
        source_chart_id=args.source_chart_id,
        chart_key=args.chart_key,
        sql_query=args.sql,
        description=args.description,
        x_guid=args.x_guid,
        x_title=args.x_title,
        y_guid=args.y_guid,
        y_title=args.y_title,
        color_guid=args.color_guid,
        color_title=args.color_title,
        validate=not args.no_validate,
        dry_run=args.dry_run,
    )
    if created.get("error") or created.get("dry_run"):
        return created
    attached = add_chart_to_dashboard(
        dashboard_id=args.dashboard_id,
        chart_id=created["chart_id"],
        widget_title=args.widget_title,
        tab_id=args.tab_id,
        position=args.position,
        anchor_chart_id=args.anchor_chart_id,
        width=args.width,
        height=args.height,
        hide_title=args.hide_title,
        publish=not args.save_only,
        grid_width=args.grid_width,
        dry_run=args.dry_run,
    )
    return {"created_chart": created, "dashboard_update": attached}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DataLens chart creation/edit helpers")
    parser.add_argument("--token-file", help="Путь к файлу с OAuth-токеном")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_sql = subparsers.add_parser("run-sql", help="Выполнить dashsql по connection")
    run_sql.add_argument("connection_id")
    run_sql.add_argument("--sql", required=True)
    run_sql.add_argument("--params", default="{}")
    run_sql.add_argument("--timeout-sec", type=float, default=20.0)

    clone = subparsers.add_parser("clone-ql-chart", help="Создать новый QL-чарт из существующего")
    clone.add_argument("source_chart_id")
    clone.add_argument("--chart-key", required=True)
    clone.add_argument("--sql", required=True)
    clone.add_argument("--description", default="")
    clone.add_argument("--x-guid")
    clone.add_argument("--x-title")
    clone.add_argument("--y-guid")
    clone.add_argument("--y-title")
    clone.add_argument("--color-guid", help="GUID поля для color dimension (stacked/grouped)")
    clone.add_argument("--color-title", help="Title поля для color dimension")
    clone.add_argument("--no-validate", action="store_true")
    clone.add_argument("--dry-run", action="store_true")

    attach = subparsers.add_parser("add-chart-to-dashboard", help="Добавить existing chart в dashboard")
    attach.add_argument("dashboard_id")
    attach.add_argument("chart_id")
    attach.add_argument("--widget-title", required=True)
    attach.add_argument("--tab-id", default="")
    attach.add_argument("--position", choices=["right", "below", "end"], default="right")
    attach.add_argument("--anchor-chart-id", default="")
    attach.add_argument("--width", type=int, default=15)
    attach.add_argument("--height", type=int, default=14)
    attach.add_argument("--grid-width", type=int, default=DEFAULT_GRID_WIDTH)
    attach.add_argument("--hide-title", action="store_true")
    attach.add_argument("--save-only", action="store_true")
    attach.add_argument("--dry-run", action="store_true")

    combined = subparsers.add_parser("clone-ql-to-dashboard", help="Создать QL-чарт и сразу привязать к dashboard")
    combined.add_argument("dashboard_id")
    combined.add_argument("source_chart_id")
    combined.add_argument("--chart-key", required=True)
    combined.add_argument("--sql", required=True)
    combined.add_argument("--widget-title", required=True)
    combined.add_argument("--description", default="")
    combined.add_argument("--tab-id", default="")
    combined.add_argument("--position", choices=["right", "below", "end"], default="right")
    combined.add_argument("--anchor-chart-id", default="")
    combined.add_argument("--width", type=int, default=15)
    combined.add_argument("--height", type=int, default=14)
    combined.add_argument("--grid-width", type=int, default=DEFAULT_GRID_WIDTH)
    combined.add_argument("--hide-title", action="store_true")
    combined.add_argument("--save-only", action="store_true")
    combined.add_argument("--x-guid")
    combined.add_argument("--x-title")
    combined.add_argument("--y-guid")
    combined.add_argument("--y-title")
    combined.add_argument("--color-guid", help="GUID поля для color dimension (stacked/grouped)")
    combined.add_argument("--color-title", help="Title поля для color dimension")
    combined.add_argument("--no-validate", action="store_true")
    combined.add_argument("--dry-run", action="store_true")

    replace = subparsers.add_parser("replace-chart-on-dashboard",
                                    help="Заменить чарт в существующем виджете dashboard")
    replace.add_argument("dashboard_id")
    replace.add_argument("old_chart_id")
    replace.add_argument("new_chart_id")
    replace.add_argument("--widget-title", default=None, help="Новый title виджета (опционально)")
    replace.add_argument("--tab-id", default="")
    replace.add_argument("--save-only", action="store_true")
    replace.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.token_file:
        _set_token_from_file(args.token_file)
    _assert_token()

    if args.command == "run-sql":
        result = run_dashsql(
            args.connection_id,
            args.sql,
            _parse_json_object(args.params, "--params"),
            timeout_sec=args.timeout_sec,
        )
    elif args.command == "clone-ql-chart":
        result = clone_ql_chart(
            source_chart_id=args.source_chart_id,
            chart_key=args.chart_key,
            sql_query=args.sql,
            description=args.description,
            x_guid=args.x_guid,
            x_title=args.x_title,
            y_guid=args.y_guid,
            y_title=args.y_title,
            color_guid=args.color_guid,
            color_title=args.color_title,
            validate=not args.no_validate,
            dry_run=args.dry_run,
        )
    elif args.command == "add-chart-to-dashboard":
        result = add_chart_to_dashboard(
            dashboard_id=args.dashboard_id,
            chart_id=args.chart_id,
            widget_title=args.widget_title,
            tab_id=args.tab_id,
            position=args.position,
            anchor_chart_id=args.anchor_chart_id,
            width=args.width,
            height=args.height,
            hide_title=args.hide_title,
            publish=not args.save_only,
            grid_width=args.grid_width,
            dry_run=args.dry_run,
        )
    elif args.command == "replace-chart-on-dashboard":
        result = replace_chart_on_dashboard(
            dashboard_id=args.dashboard_id,
            old_chart_id=args.old_chart_id,
            new_chart_id=args.new_chart_id,
            widget_title=args.widget_title,
            tab_id=args.tab_id,
            publish=not args.save_only,
            dry_run=args.dry_run,
        )
    else:
        result = clone_ql_to_dashboard(args)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
