#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone


TRACKER_BASE_URL = "https://st-api.yandex-team.ru/v3"
TRACKER_WEB_URL = "https://st.yandex-team.ru"
ARCANUM_BASE_URL = "https://arcanum.yandex.net/api"
ARCANUM_WEB_URL = "https://a.yandex-team.ru/review"
DONE_STATUS_KEYS = {
    "closed",
    "done",
    "fixed",
    "resolved",
    "released",
    "testing_done",
    "verified",
}


class RequestError(Exception):
    pass


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except FileNotFoundError:
        return ""


def get_tracker_token():
    token = os.environ.get("TRACKER_OAUTH_TOKEN", "").strip()
    if token:
        return token
    token = read_file(os.path.expanduser("~/.tracker-token"))
    if token:
        return token
    fail("No Tracker token found. Set TRACKER_OAUTH_TOKEN or save it to ~/.tracker-token")


def get_arc_token():
    token = os.environ.get("ARC_OAUTH_TOKEN", "").strip()
    if token:
        return token
    token = read_file(os.path.expanduser("~/.arc/token"))
    if token:
        return token

    arcadia_root = os.environ.get("ARCADIA_ROOT_OVERRIDE") or os.path.expanduser("~/arcadia")
    try:
        result = subprocess.run(
            ["arc", "token", "show"],
            cwd=arcadia_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        result = None

    if result and result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    fail("No Arcanum token found. Set ARC_OAUTH_TOKEN, save it to ~/.arc/token, or ensure `arc token show` works")


def sanitize_json_bytes(raw_bytes):
    text = raw_bytes.decode("utf-8", errors="replace")
    return "".join(ch if ord(ch) >= 32 or ch in "\n\r\t" else " " for ch in text)


def http_request_json(method, url, headers, body=None, unwrap_data=False, sanitize=False):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    attempts = 3
    raw = None
    last_error = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, data=data, method=method)
        for key, value in headers.items():
            request.add_header(key, value)

        try:
            with urllib.request.urlopen(request) as response:
                raw = response.read()
                break
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace").strip()
            if error.code == 429 and attempt < attempts - 1:
                retry_after = error.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else 2 ** attempt
                except ValueError:
                    delay = 2 ** attempt
                time.sleep(max(delay, 1.0))
                last_error = f"HTTP {error.code} for {url}: {details}"
                continue
            raise RequestError(f"HTTP {error.code} for {url}: {details}")
        except urllib.error.URLError as error:
            raise RequestError(f"Request failed for {url}: {error}")

    if raw is None:
        raise RequestError(last_error or f"Request failed for {url}")

    text = sanitize_json_bytes(raw) if sanitize else raw.decode("utf-8", errors="replace")
    payload = json.loads(text)
    return payload.get("data") if unwrap_data else payload


def tracker_headers():
    return {
        "Authorization": f"OAuth {get_tracker_token()}",
        "Content-Type": "application/json",
    }


def arcanum_headers():
    return {
        "Authorization": f"OAuth {get_arc_token()}",
        "Content-Type": "application/json",
    }


def tracker_get(path):
    return http_request_json("GET", f"{TRACKER_BASE_URL}{path}", tracker_headers(), sanitize=True)


def tracker_post(path, body):
    return http_request_json("POST", f"{TRACKER_BASE_URL}{path}", tracker_headers(), body=body, sanitize=True)


def arcanum_get(path):
    return http_request_json("GET", f"{ARCANUM_BASE_URL}{path}", arcanum_headers(), unwrap_data=True)


def parse_dt(value):
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_date_only(value):
    dt = parse_dt(value)
    return dt.date() if dt else None


def current_period(today=None):
    today = today or date.today()
    if today.month <= 6:
        return {
            "year": today.year,
            "half": 1,
            "label": f"{today.year} H1 (январь-июнь)",
            "start": date(today.year, 1, 1),
            "end": date(today.year, 6, 30),
        }
    return {
        "year": today.year,
        "half": 2,
        "label": f"{today.year} H2 (июль-декабрь)",
        "start": date(today.year, 7, 1),
        "end": date(today.year, 12, 31),
    }


def build_period(year=None, half=None):
    if year is None and half is None:
        return current_period()
    if year is None or half is None:
        fail("Use both --year and --half together")
    if half == 1:
        return {
            "year": year,
            "half": 1,
            "label": f"{year} H1 (январь-июнь)",
            "start": date(year, 1, 1),
            "end": date(year, 6, 30),
        }
    if half == 2:
        return {
            "year": year,
            "half": 2,
            "label": f"{year} H2 (июль-декабрь)",
            "start": date(year, 7, 1),
            "end": date(year, 12, 31),
        }
    fail("Half must be 1 or 2")


def russian_period_label(period):
    if period["half"] == 1:
        return f"{period['start'].strftime('%d.%m.%Y')} - {period['end'].strftime('%d.%m.%Y')} (январь-июнь {period['year']})"
    return f"{period['start'].strftime('%d.%m.%Y')} - {period['end'].strftime('%d.%m.%Y')} (июль-декабрь {period['year']})"


def russian_date(value):
    parsed = parse_date_only(value) if isinstance(value, str) else value
    if not parsed:
        return "дата не указана"
    return parsed.strftime("%d.%m.%Y")


def plural(value, one, few, many):
    mod10 = value % 10
    mod100 = value % 100
    if mod10 == 1 and mod100 != 11:
        return one
    if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
        return few
    return many


def tracker_search_all(query, start_date, max_pages):
    results = []
    for page in range(1, max_pages + 1):
        page_data = tracker_post(
            f"/issues/_search?perPage=100&page={page}&orderBy=-updatedAt",
            {"query": query},
        )
        if not page_data:
            break
        results.extend(page_data)

        oldest_updated = None
        for issue in page_data:
            updated = parse_date_only(issue.get("updatedAt"))
            if updated and (oldest_updated is None or updated < oldest_updated):
                oldest_updated = updated
        if oldest_updated and oldest_updated < start_date:
            break
    return results


def issue_done_in_period(issue, start_date, end_date):
    resolved_date = parse_date_only(
        issue.get("resolvedAt")
        or issue.get("resolved")
        or issue.get("resolutionDate")
        or issue.get("resolutionTime")
    )
    updated_date = parse_date_only(issue.get("updatedAt"))

    if resolved_date:
        return start_date <= resolved_date <= end_date

    status_key = ((issue.get("status") or {}).get("key") or "").lower()
    resolution_present = bool(issue.get("resolution"))
    if (resolution_present or status_key in DONE_STATUS_KEYS) and updated_date and start_date <= updated_date <= end_date:
        return True

    return False


def tracker_issue(key, cache):
    if key not in cache:
        cache[key] = tracker_get(f"/issues/{key}")
    return cache[key]


def tracker_remote_links(key, cache):
    if key not in cache:
        cache[key] = tracker_get(f"/issues/{key}/remotelinks")
    return cache[key]


def arcanum_pr(pr_id, cache):
    if pr_id not in cache:
        try:
            cache[pr_id] = arcanum_get(
                f"/v1/pull-requests/{pr_id}?fields=id,url,summary,status,created_at,updated_at,merged_at,vcs(from_branch,to_branch)"
            )
        except RequestError as error:
            print(f"WARN: failed to fetch PR #{pr_id}: {error}", file=sys.stderr)
            cache[pr_id] = {
                "id": pr_id,
                "url": f"{ARCANUM_WEB_URL}/{pr_id}",
                "summary": "",
                "status": "",
                "merged_at": None,
            }
    return cache[pr_id]


def extract_pr_ids(remote_links):
    pr_ids = []
    seen = set()
    for item in remote_links or []:
        application_type = (((item.get("object") or {}).get("application") or {}).get("type") or "")
        key = ((item.get("object") or {}).get("key") or "")
        url = ((item.get("object") or {}).get("url") or item.get("url") or "")
        candidate_ids = []

        if application_type == "ru.yandex.arcanum" and str(key).isdigit():
            candidate_ids.append(str(key))

        if url:
            for match in re.findall(r"/review/(\d+)", url):
                candidate_ids.append(match)

        for pr_id in candidate_ids:
            if pr_id not in seen:
                seen.add(pr_id)
                pr_ids.append(pr_id)
    return pr_ids


def first_non_empty(values):
    for value in values:
        if value:
            return value
    return ""


def get_parent_label(issue, issue_cache):
    parent = issue.get("parent") or {}
    parent_key = parent.get("key")
    if not parent_key:
        return ""
    parent_issue = tracker_issue(parent_key, issue_cache)
    return f"{parent_key} - {parent_issue.get('summary', '').strip()}".strip()


def get_project_label(issue):
    project = issue.get("project") or {}
    primary = project.get("primary") or {}
    return first_non_empty([primary.get("display"), primary.get("name"), primary.get("id")])


def get_component_labels(issue):
    components = issue.get("components") or []
    labels = []
    for component in components:
        label = first_non_empty([component.get("display"), component.get("name"), component.get("id")])
        if label:
            labels.append(label)
    return labels


def derive_goal(issue, issue_cache):
    parent_label = get_parent_label(issue, issue_cache)
    if parent_label:
        return parent_label, "parent"

    project_label = get_project_label(issue)
    if project_label:
        return project_label, "project"

    component_labels = get_component_labels(issue)
    if component_labels:
        return ", ".join(component_labels[:2]), "components"

    queue = (issue.get("queue") or {}).get("key")
    return queue or "Прочие задачи", "queue"


def build_ticket_entry(issue, issue_cache, remote_links_cache, pr_cache):
    key = issue.get("key")
    remote_links = tracker_remote_links(key, remote_links_cache)
    pr_ids = extract_pr_ids(remote_links)
    prs = []
    for pr_id in pr_ids:
        pr = arcanum_pr(pr_id, pr_cache)
        prs.append(
            {
                "id": str(pr.get("id") or pr_id),
                "url": pr.get("url") or f"{ARCANUM_WEB_URL}/{pr_id}",
                "summary": pr.get("summary") or "",
                "status": pr.get("status") or "",
                "merged_at": pr.get("merged_at"),
            }
        )

    goal_label, goal_source = derive_goal(issue, issue_cache)
    return {
        "key": key,
        "url": f"{TRACKER_WEB_URL}/{key}",
        "summary": issue.get("summary") or "",
        "status": first_non_empty([
            (issue.get("status") or {}).get("display"),
            (issue.get("status") or {}).get("key"),
        ]),
        "resolved_at": issue.get("resolvedAt") or issue.get("resolved") or issue.get("resolutionDate") or issue.get("updatedAt"),
        "updated_at": issue.get("updatedAt"),
        "project": get_project_label(issue),
        "components": get_component_labels(issue),
        "goal": goal_label,
        "goal_source": goal_source,
        "prs": prs,
    }


def collect_data(args):
    period = build_period(args.year, args.half)
    login = (args.login or os.environ.get("SELF_REVIEW_LOGIN") or os.environ.get("USER") or "").strip()
    query = args.query or (f"assignee:{login}" if login else "assignee:me()")

    raw_issues = tracker_search_all(query, period["start"], args.max_pages)
    candidate_keys = []
    seen_keys = set()
    for issue in raw_issues:
        key = issue.get("key")
        updated = parse_date_only(issue.get("updatedAt"))
        if not key or not updated:
            continue
        if updated < period["start"]:
            continue
        if key not in seen_keys:
            seen_keys.add(key)
            candidate_keys.append(key)

    issue_cache = {}
    remote_links_cache = {}
    pr_cache = {}
    tickets = []

    for key in candidate_keys:
        issue = tracker_issue(key, issue_cache)
        if issue_done_in_period(issue, period["start"], period["end"]):
            tickets.append(build_ticket_entry(issue, issue_cache, remote_links_cache, pr_cache))

    tickets.sort(key=lambda item: (item["resolved_at"] or "", item["key"]), reverse=True)

    goals = defaultdict(lambda: {"source": "", "tickets": [], "prs": []})
    unique_pr_ids = set()
    for ticket in tickets:
        goal = goals[ticket["goal"]]
        goal["source"] = ticket["goal_source"]
        goal["tickets"].append(ticket)
        for pr in ticket["prs"]:
            if pr["id"] not in {item["id"] for item in goal["prs"]}:
                goal["prs"].append(pr)
            unique_pr_ids.add(pr["id"])

    goal_items = []
    for name, payload in goals.items():
        goal_items.append(
            {
                "name": name,
                "source": payload["source"],
                "ticket_count": len(payload["tickets"]),
                "pr_count": len(payload["prs"]),
                "tickets": payload["tickets"],
                "prs": payload["prs"],
            }
        )

    goal_items.sort(key=lambda item: (-item["ticket_count"], item["name"].lower()))

    return {
        "login": login or "me()",
        "query": query,
        "period": {
            "year": period["year"],
            "half": period["half"],
            "label": period["label"],
            "start": period["start"].isoformat(),
            "end": period["end"].isoformat(),
            "human": russian_period_label(period),
        },
        "stats": {
            "raw_issues": len(raw_issues),
            "candidate_issues": len(candidate_keys),
            "completed_issues": len(tickets),
            "goals": len(goal_items),
            "unique_prs": len(unique_pr_ids),
        },
        "goals": goal_items,
        "tickets": tickets,
    }


def format_pr_links(prs):
    if not prs:
        return "без связанных PR"
    return ", ".join(f"[PR #{pr['id']}]({pr['url']})" for pr in prs)


def format_ticket_links(tickets):
    return ", ".join(f"[{ticket['key']}]({ticket['url']})" for ticket in tickets)


def draft_text(data):
    period = data["period"]
    stats = data["stats"]
    tickets = data["tickets"]
    goals = data["goals"]

    if not tickets:
        return (
            f"За период {period['human']} не удалось автоматически найти завершенные задачи по запросу `{data['query']}`.\n\n"
            "Что можно сделать дальше:\n"
            f"- проверить логин и повторить с `--login`\n"
            f"- сузить или расширить выборку через `--query`\n"
            f"- попробовать соседний период через `--year` и `--half`"
        )

    intro = (
        f"За период {period['human']} я завершил {stats['completed_issues']} "
        f"{plural(stats['completed_issues'], 'задачу', 'задачи', 'задач')} в Tracker и довел до результата "
        f"{stats['unique_prs']} {plural(stats['unique_prs'], 'связанный PR', 'связанных PR', 'связанных PR')} в Arcanum. "
        f"Основная работа была сгруппирована вокруг {stats['goals']} "
        f"{plural(stats['goals'], 'цели', 'целей', 'целей')}."
    )

    lines = [intro, "", "Ключевые достигнутые цели:"]
    for goal in goals:
        ticket_links = format_ticket_links(goal["tickets"])
        pr_links = format_pr_links(goal["prs"])
        lines.append(
            f"- {goal['name']}: завершил {goal['ticket_count']} "
            f"{plural(goal['ticket_count'], 'задачу', 'задачи', 'задач')} ({ticket_links}); {pr_links}."
        )

    lines.extend(["", "Выполненные задачи:"])
    for ticket in tickets:
        pr_suffix = ""
        if ticket["prs"]:
            pr_suffix = f" PR: {format_pr_links(ticket['prs'])}."
        lines.append(
            f"- [{ticket['key']}]({ticket['url']}) - {ticket['summary']}. "
            f"Цель: {ticket['goal']}. Статус: {ticket['status']}. "
            f"Закрыта/обновлена: {russian_date(ticket['resolved_at'])}.{pr_suffix}"
        )

    lines.extend(
        [
            "",
            "Примечание: цели сгруппированы автоматически по родительским задачам, проектам или компонентам. "
            "При необходимости этот черновик стоит вручную дополнить влиянием, метриками и контекстом.",
        ]
    )
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(prog="python3 scripts/self_review.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_options(subparser):
        subparser.add_argument("--login", help="Tracker login; default is SELF_REVIEW_LOGIN or USER")
        subparser.add_argument("--query", help="Custom Tracker query instead of assignee-based default")
        subparser.add_argument("--year", type=int, help="Report year")
        subparser.add_argument("--half", type=int, choices=[1, 2], help="1 = Jan-Jun, 2 = Jul-Dec")
        subparser.add_argument("--max-pages", type=int, default=20, help="Maximum number of Tracker search pages")

    period_parser = subparsers.add_parser("period", help="Show reporting period")
    period_parser.add_argument("--year", type=int, help="Report year")
    period_parser.add_argument("--half", type=int, choices=[1, 2], help="1 = Jan-Jun, 2 = Jul-Dec")
    period_parser.add_argument("--json", action="store_true", help="Output JSON")

    collect_parser = subparsers.add_parser("collect", help="Collect structured self-review data")
    add_common_options(collect_parser)
    collect_parser.add_argument("--json", action="store_true", help="Output JSON")

    draft_parser = subparsers.add_parser("draft", help="Generate Russian self-review draft")
    add_common_options(draft_parser)
    draft_parser.add_argument("--json", action="store_true", help="Output collected JSON instead of text")

    return parser


def command_period(args):
    period = build_period(args.year, args.half)
    payload = {
        "year": period["year"],
        "half": period["half"],
        "label": period["label"],
        "start": period["start"].isoformat(),
        "end": period["end"].isoformat(),
        "human": russian_period_label(period),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload["human"])


def command_collect(args):
    data = collect_data(args)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def command_draft(args):
    data = collect_data(args)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(draft_text(data))


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "period":
            command_period(args)
        elif args.command == "collect":
            command_collect(args)
        elif args.command == "draft":
            command_draft(args)
        else:
            parser.error(f"Unknown command: {args.command}")
    except RequestError as error:
        fail(str(error))


if __name__ == "__main__":
    main()
