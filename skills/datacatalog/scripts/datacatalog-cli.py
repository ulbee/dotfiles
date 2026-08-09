#!/usr/bin/env python3
"""DataCatalog CLI — wrapper around data.yandex-team.ru portal API"""

import sys
import os
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
import ssl

BASE_URL = "https://data.yandex-team.ru"

# Skip SSL verification (same as MCP server: verify=False)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def get_token():
    token = os.environ.get("DATACATALOG_TOKEN") or os.environ.get("DC_TOKEN")
    if token:
        return token.strip()
    token_file = os.path.expanduser("~/.datacatalog_token")
    if os.path.exists(token_file):
        return open(token_file).read().strip()
    print("ERROR: No OAuth token found.", file=sys.stderr)
    print("Set DATACATALOG_TOKEN env var or save token to ~/.datacatalog_token", file=sys.stderr)
    sys.exit(1)


def api_get(token, path, params=None):
    url = BASE_URL + path
    if params:
        url += "?" + urlencode(params)
    req = Request(url, headers={
        "Authorization": f"OAuth {token}",
        "Accept": "application/json",
    })
    try:
        with urlopen(req, context=SSL_CTX, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"HTTP {e.code} {e.reason}: {body}", file=sys.stderr)
        sys.exit(1)


def api_post(token, path, body):
    url = BASE_URL + path
    data = json.dumps(body).encode()
    req = Request(url, data=data, headers={
        "Authorization": f"OAuth {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urlopen(req, context=SSL_CTX, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"HTTP {e.code} {e.reason}: {body}", file=sys.stderr)
        sys.exit(1)


def build_search_body(query, cluster=None):
    return {
        "search_filter": {
            "vertical": ["data_entity", "article", "domain"],
            "text": query,
            "common_filter": {
                "owner": [], "responsible": [], "editor": [],
                "domain_path": [], "attributes": [],
            },
            "data_entity_filter": {
                "system": [],
                "cluster": [cluster] if cluster else None,
            },
        },
        "limit": 5,
        "page": 0,
        "is_regex": False,
        "resolve_query": True,
        "fast_search": True,
    }


def cmd_search(token, query, cluster=None):
    """Search data entities by text query."""
    res = api_post(token, "/portal/api/v1/search", build_search_body(query, cluster))

    if not res.get("items"):
        print("No results found. Suggestions:")
        print("- Try simplifying the search query")
        print("- Verify you have access to the resources")
        print("- Check if the YT cluster is correct (if searching for tables)")
        return

    print("data_entity_id|slug|logtype")
    for item in res["items"]:
        if item.get("entity_type") != "data_entity":
            continue
        data_entity_id = item.get("id", "N/A")
        slug = item.get("slug", "N/A")
        logtype = "N/A"
        if "Logos" in item.get("externalLinks", {}):
            log_match = re.search(r"(log=\[.*\])", item["externalLinks"]["Logos"])
            if log_match:
                logtype = (log_match.group(1)
                           .replace("log=", "")
                           .replace("['", "")
                           .replace("']", ""))
        print(f"{data_entity_id}|{slug}|{logtype}")


def _get_slug_parts(slug):
    """Parse yt://cluster?path=//... into (cluster, path)."""
    m = re.match(r'^yt://([^?]+)\?path=(.+)$', slug)
    if m:
        return m.group(1), m.group(2)
    # Fallback
    return "hahn", re.sub(r'^yt://[^?]+\?path=', '', slug)


def _format_column_type(type_str):
    return re.sub(r'(optional)|\\', '', type_str).strip()


def _format_description(title, description):
    text = ' '.join(filter(None, [title, description]))
    return re.sub(r'\s+', ' ', text).strip()


def _print_schema(fields):
    print("name|type|description")
    for f in fields:
        glossary = f.get("glossaryEntity", {})
        title = glossary.get("title", "")
        desc = glossary.get("description", "")
        print(f"{f.get('name', '')}|{_format_column_type(f.get('type', ''))}|{_format_description(title, desc)}")


def cmd_schema_by_path(token, path):
    """Get table schema by YT path (must start with //)."""
    if not path.startswith("//"):
        print(f"ERROR: path must start with '//', got: {path}", file=sys.stderr)
        sys.exit(1)

    # Step 1: search for entity by path (use hahn as default cluster)
    body = build_search_body(path, cluster="hahn")
    body["search_filter"]["vertical"] = ["data_entity"]
    res = api_post(token, "/portal/api/v1/search", body)

    items = res.get("items", [])
    if not items:
        print(f"No data entities found for path: {path}", file=sys.stderr)
        sys.exit(1)

    data_entity_id = items[0]["id"]

    # Step 2: get entity details to resolve cluster and full path
    de = api_get(token, f"/portal/api/v1/data_entity/{data_entity_id}")
    cluster, full_path = _get_slug_parts(de["slug"])

    # Step 3: fetch schema
    schema_data = api_get(token, "/portal/api/v1/data_entity/schema", {
        "path": full_path, "type": "yt", "cluster": cluster,
    })
    _print_schema(schema_data["schema"]["fields"])
    print(f"data_entity_id: {data_entity_id}")


def cmd_schema_by_id(token, data_entity_id):
    """Get table schema by data entity ID."""
    de = api_get(token, f"/portal/api/v1/data_entity/{data_entity_id}")
    cluster, full_path = _get_slug_parts(de["slug"])

    schema_data = api_get(token, "/portal/api/v1/data_entity/schema", {
        "path": full_path, "type": "yt", "cluster": cluster,
    })
    _print_schema(schema_data["schema"]["fields"])
    print(f"table_path: {full_path}")

    if "logos" in de.get("attributes", {}):
        logtype = de["attributes"]["logos"]["logtype"]["values"][0]
        print(f"Logtype: {logtype}")


def cmd_description(token, data_entity_id):
    """Get text description of a data entity."""
    de = api_get(token, f"/portal/api/v1/data_entity/{data_entity_id}")
    table_path = re.sub(r'^yt://[^?]+\?path=', '', de["slug"])

    descriptions = de.get("descriptions", {})
    default_type = de.get("defaultDescriptionType")

    if not descriptions:
        print("No description available.")
    else:
        desc_entry = descriptions.get(default_type) if default_type else None
        if desc_entry is None:
            desc_entry = next(iter(descriptions.values()))

        glossary = desc_entry.get("glossary", {})
        title = glossary.get("title", "")
        desc = glossary.get("description", "")

        parts = []
        if title:
            parts.append(f"Title: {title}")
        if desc:
            parts.append(desc)

        print("\n\n".join(parts) if parts else "No description available.")

    print(f"\ntable_path: {table_path}")


def _usage_time_window():
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=2)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    return start.strftime("%Y-%m-%dT%H:%M:%S"), end.strftime("%Y-%m-%dT%H:%M:%S")


def cmd_usage_columns(token, data_entity_id):
    """Get columns recently used in queries for a data entity."""
    start_ts, end_ts = _usage_time_window()
    body = {
        "data_entity_id": [int(data_entity_id)],
        "start_usage_time": start_ts,
        "end_usage_time": end_ts,
    }
    raw = api_post(token, "/portal/api/v1/entity_usage/columns", body)

    if not raw:
        print("No column usage data found for the given data entity.")
        return

    for entry in raw:
        columns = entry.get("columns", [])
        print(f"data_entity_id: {entry.get('data_entity_id')}")
        print(f"used columns ({len(columns)}):")
        for col in columns:
            print(f"  {col}")


def cmd_usage_sources(token, data_entity_id, direction):
    """Get parent or child sources for a data entity."""
    input_source = (direction == "parents")
    start_ts, end_ts = _usage_time_window()

    params = {
        "data_entity_ids": int(data_entity_id),
        "input_source": str(input_source).lower(),
        "start_ts": start_ts,
        "end_ts": end_ts,
        "limit": 100,
        "page": 0,
    }
    raw = api_get(token, "/portal/api/v1/entity_usage/sources", params)

    dir_name = "parent" if direction == "parents" else "child"
    items = raw.get("items", [])
    if not items:
        print(f"No {dir_name} sources found.")
        return

    print(f"{dir_name} sources (total: {raw.get('total', 0)}):")
    print("data_entity_id|slug|owners")
    for item in items:
        owners = ", ".join(item.get("owners", []))
        print(f"{item.get('dataEntityId')}|{item.get('slug')}|{owners}")


HELP = """\
DataCatalog CLI — data.yandex-team.ru

Commands:
  search <query>                       Search data entities by text query
  search-in-cluster <query> <cluster>  Search with cluster filter (hahn/arnold/kolmogorov)
  schema-by-path <//yt/path>           Get table schema by YT path
  schema-by-id <data_entity_id>        Get table schema by data entity ID
  description <data_entity_id>         Get table description
  usage-columns <data_entity_id>       Get recently used columns (last 2 days)
  usage-parents <data_entity_id>       Get parent (input) tables
  usage-children <data_entity_id>      Get child (output) tables

Auth:
  Set DATACATALOG_TOKEN env var or save OAuth token to ~/.datacatalog_token

Examples:
  datacatalog-cli.py search "grut_enriched/assets"
  datacatalog-cli.py search-in-cluster "product_money" hahn
  datacatalog-cli.py schema-by-path //statbox/cube/daily/grut_enriched/assets/2025-02-11
  datacatalog-cli.py schema-by-id 2045844082
  datacatalog-cli.py description 2045844082
  datacatalog-cli.py usage-columns 2045844082
  datacatalog-cli.py usage-parents 2045844082
  datacatalog-cli.py usage-children 2045844082
"""


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("help", "--help", "-h"):
        print(HELP)
        return

    token = get_token()
    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "search":
        if not args:
            print("Usage: datacatalog-cli.py search <query>", file=sys.stderr)
            sys.exit(1)
        cmd_search(token, args[0])

    elif cmd == "search-in-cluster":
        if len(args) < 2:
            print("Usage: datacatalog-cli.py search-in-cluster <query> <cluster>", file=sys.stderr)
            sys.exit(1)
        cmd_search(token, args[0], cluster=args[1])

    elif cmd == "schema-by-path":
        if not args:
            print("Usage: datacatalog-cli.py schema-by-path <//yt/path>", file=sys.stderr)
            sys.exit(1)
        cmd_schema_by_path(token, args[0])

    elif cmd == "schema-by-id":
        if not args:
            print("Usage: datacatalog-cli.py schema-by-id <data_entity_id>", file=sys.stderr)
            sys.exit(1)
        cmd_schema_by_id(token, args[0])

    elif cmd == "description":
        if not args:
            print("Usage: datacatalog-cli.py description <data_entity_id>", file=sys.stderr)
            sys.exit(1)
        cmd_description(token, args[0])

    elif cmd == "usage-columns":
        if not args:
            print("Usage: datacatalog-cli.py usage-columns <data_entity_id>", file=sys.stderr)
            sys.exit(1)
        cmd_usage_columns(token, args[0])

    elif cmd == "usage-parents":
        if not args:
            print("Usage: datacatalog-cli.py usage-parents <data_entity_id>", file=sys.stderr)
            sys.exit(1)
        cmd_usage_sources(token, args[0], "parents")

    elif cmd == "usage-children":
        if not args:
            print("Usage: datacatalog-cli.py usage-children <data_entity_id>", file=sys.stderr)
            sys.exit(1)
        cmd_usage_sources(token, args[0], "children")

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(HELP, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
