#!/usr/bin/env python3
"""SkillStore tool runner — stdlib-only CLI for SkillStore API.

No external Python dependencies required.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from typing import Any
from urllib import error, parse, request


DEFAULT_BASE_URL = "https://dab512.aimarvel.yandex.net"
API_PREFIX = "/skillstore/api"


class SkillStoreError(RuntimeError):
    pass


class SkillStoreHTTP:
    def __init__(self, base_url: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, endpoint: str) -> str:
        return f"{self.base_url}{API_PREFIX}/{endpoint}"

    def get(self, endpoint: str, params: dict | None = None) -> Any:
        url = self._url(endpoint)
        if params:
            url += "?" + parse.urlencode(params)
        req = request.Request(url, method="GET")
        return self._do(req)

    def post_json(self, endpoint: str, data: dict) -> Any:
        url = self._url(endpoint)
        body = json.dumps(data).encode("utf-8")
        req = request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        return self._do(req)

    def post_multipart(self, endpoint: str, fields: dict, file_field: str = "", file_path: str = "") -> Any:
        boundary = "----SkillStoreBoundary9876543210"
        body = b""

        for key, value in fields.items():
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
            body += f"{value}\r\n".encode()

        if file_field and file_path:
            filename = os.path.basename(file_path)
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode()
            body += b"Content-Type: application/octet-stream\r\n\r\n"
            with open(file_path, "rb") as f:
                body += f.read()
            body += b"\r\n"

        body += f"--{boundary}--\r\n".encode()

        url = self._url(endpoint)
        req = request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        return self._do(req)

    def download(self, endpoint: str, params: dict, output_path: str) -> str:
        url = self._url(endpoint)
        if params:
            url += "?" + parse.urlencode(params)
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                # Get filename from Content-Disposition header
                cd = resp.headers.get("Content-Disposition", "")
                fname = "download"
                if "filename=" in cd:
                    fname = cd.split("filename=")[-1].strip('"')
                dest = os.path.join(output_path, fname)
                with open(dest, "wb") as f:
                    f.write(resp.read())
                return dest
        except error.HTTPError as e:
            raise SkillStoreError(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}") from e

    def _do(self, req: request.Request) -> Any:
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw.strip() else {}
        except error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            try:
                err = json.loads(body)
                msg = err.get("error", body)
            except json.JSONDecodeError:
                msg = body
            raise SkillStoreError(f"HTTP {e.code}: {msg}") from e


# ---------- Tools ----------

def _make_zip(path: str) -> str:
    """Pack file or directory into a zip archive, return path to zip."""
    if os.path.isfile(path) and path.endswith(".zip"):
        return path

    tmp = tempfile.mktemp(suffix=".zip")

    if os.path.isdir(path):
        parent = os.path.dirname(os.path.abspath(path))
        dirname = os.path.basename(os.path.abspath(path))
        subprocess.check_call(
            ["zip", "-r", tmp, dirname,
             "-x", "*__pycache__*", "*.pyc", "*.pyo", "*/.DS_Store"],
            cwd=parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.check_call(["zip", "-j", tmp, path],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return tmp


def list_skills(http: SkillStoreHTTP, params: dict) -> Any:
    """List skills with optional filtering."""
    query = {}
    if params.get("search"):
        query["search"] = params["search"]
    if params.get("regex"):
        query["regex"] = "1"
    if params.get("category"):
        query["category"] = params["category"]
    if params.get("tag"):
        query["tag"] = params["tag"]
    if params.get("sort"):
        query["sort"] = params["sort"]
    if params.get("author"):
        query["author"] = params["author"]
    query["page"] = params.get("page", 1)
    query["per_page"] = params.get("per_page", 50)
    return http.get("endpoint_skills_list", query)


def search_skills(http: SkillStoreHTTP, params: dict) -> Any:
    """Search skills by text or regex."""
    query = {"per_page": params.get("per_page", 50)}
    if params.get("query"):
        query["search"] = params["query"]
    if params.get("regex"):
        query["regex"] = "1"
    if params.get("tag"):
        query["tag"] = params["tag"]
    if params.get("category"):
        query["category"] = params["category"]
    if params.get("sort"):
        query["sort"] = params["sort"]
    return http.get("endpoint_skills_list", query)


def get_skill(http: SkillStoreHTTP, params: dict) -> Any:
    """Get skill details by slug."""
    slug = params.get("slug", "")
    if not slug:
        raise SkillStoreError("Parameter 'slug' is required")
    return http.get("endpoint_skills_get", {"slug": slug})


def create_skill(http: SkillStoreHTTP, params: dict) -> Any:
    """Create a new skill. Accepts file or directory path — auto-packs to zip."""
    path = params.get("path", "")
    if not path:
        raise SkillStoreError("Parameter 'path' is required")
    if not os.path.exists(path):
        raise SkillStoreError(f"Path not found: {path}")

    name = params.get("name", "")
    description = params.get("description", "")
    author_name = params.get("author_name", "")

    if not name:
        raise SkillStoreError("Parameter 'name' is required")
    if not description:
        raise SkillStoreError("Parameter 'description' is required")
    if not author_name:
        raise SkillStoreError("Parameter 'author_name' is required")

    zip_path = _make_zip(path)

    fields = {
        "name": name,
        "description": description,
        "author_name": author_name,
    }
    for key in ("short_description", "category_path"):
        if params.get(key):
            fields[key] = params[key]
    if params.get("tags"):
        fields["tags"] = json.dumps(params["tags"]) if isinstance(params["tags"], list) else params["tags"]

    try:
        return http.post_multipart("endpoint_skills_create", fields, "archive", zip_path)
    finally:
        if zip_path != path and os.path.exists(zip_path):
            os.unlink(zip_path)




def delete_skill(http: SkillStoreHTTP, params: dict) -> Any:
    """Delete a skill by slug."""
    slug = params.get("slug", "")
    if not slug:
        raise SkillStoreError("Parameter 'slug' is required")
    fields: dict[str, Any] = {"slug": slug}
    if params.get("auth"):
        fields["auth"] = params["auth"]
    return http.post_json("endpoint_skills_delete", fields)


def move_skills(http: SkillStoreHTTP, params: dict) -> Any:
    """Move skills to a different category."""
    slugs = params.get("slugs", [])
    category_path = params.get("category_path", "")
    if not slugs:
        raise SkillStoreError("Parameter 'slugs' is required (list)")
    return http.post_json("endpoint_skills_bulk_move", {
        "slugs": slugs,
        "category_path": category_path,
    })


def download_skill(http: SkillStoreHTTP, params: dict) -> dict:
    """Download skill archive. Optionally specify version number."""
    slug = params.get("slug", "")
    if not slug:
        raise SkillStoreError("Parameter 'slug' is required")
    version = params.get("version")
    output_dir = params.get("output_dir", "/tmp")
    os.makedirs(output_dir, exist_ok=True)
    endpoint = "endpoint_versions_download" if version else "endpoint_skills_download"
    dl_params = {"slug": slug}
    if version:
        dl_params["version"] = version
    dest = http.download(endpoint, dl_params, output_dir)
    return {"downloaded": dest, "size": os.path.getsize(dest)}


def suggest_category(http: SkillStoreHTTP, params: dict) -> Any:
    """AI-powered category suggestion."""
    name = params.get("name", "")
    description = params.get("description", "")
    if not name or not description:
        raise SkillStoreError("Parameters 'name' and 'description' are required")
    return http.post_json("endpoint_skills_suggest", {
        "name": name,
        "description": description,
    })


def list_categories(http: SkillStoreHTTP, _params: dict) -> Any:
    """Get category tree."""
    return http.get("endpoint_categories_list")


def create_category(http: SkillStoreHTTP, params: dict) -> Any:
    """Create a new category."""
    path = params.get("path", "")
    display_name = params.get("display_name", "")
    description = params.get("description", "")
    if not path or not display_name or not description:
        raise SkillStoreError("Parameters 'path', 'display_name', 'description' are required")
    data = {"path": path, "display_name": display_name, "description": description}
    if params.get("icon"):
        data["icon"] = params["icon"]
    return http.post_json("endpoint_categories_create", data)


def update_category(http: SkillStoreHTTP, params: dict) -> Any:
    """Update a category."""
    path = params.get("path", "")
    if not path:
        raise SkillStoreError("Parameter 'path' is required")
    data = {"path": path}
    for key in ("display_name", "description", "icon"):
        if key in params:
            data[key] = params[key]
    return http.post_json("endpoint_categories_update", data)


def delete_category(http: SkillStoreHTTP, params: dict) -> Any:
    """Delete a category with optional skill migration."""
    path = params.get("path", "")
    if not path:
        raise SkillStoreError("Parameter 'path' is required")
    data = {"path": path}
    if "move_skills_to" in params:
        data["move_skills_to"] = params["move_skills_to"]
    return http.post_json("endpoint_categories_delete", data)


def get_stats(http: SkillStoreHTTP, _params: dict) -> Any:
    """Get catalog statistics."""
    return http.get("endpoint_stats")


# ---------- Versions ----------

def list_versions(http: SkillStoreHTTP, params: dict) -> Any:
    """List all versions of a skill."""
    slug = params.get("slug", "")
    if not slug:
        raise SkillStoreError("Parameter 'slug' is required")
    return http.get("endpoint_versions_list", {"slug": slug})


def create_version(http: SkillStoreHTTP, params: dict) -> Any:
    """Create a new version. File is optional — omit 'path' to update metadata only."""
    slug = params.get("slug", "")
    path = params.get("path", "")
    uploaded_by = params.get("uploaded_by", "")
    if not slug:
        raise SkillStoreError("Parameter 'slug' is required")
    if not uploaded_by:
        raise SkillStoreError("Parameter 'uploaded_by' is required")

    fields = {
        "slug": slug,
        "uploaded_by": uploaded_by,
    }
    for key in ("uploaded_by_display", "changelog", "description", "short_description"):
        if params.get(key):
            fields[key] = params[key]
    if params.get("tags"):
        fields["tags"] = json.dumps(params["tags"]) if isinstance(params["tags"], list) else params["tags"]

    zip_path = ""
    if path:
        if not os.path.exists(path):
            raise SkillStoreError(f"Path not found: {path}")
        zip_path = _make_zip(path)

    try:
        if zip_path:
            return http.post_multipart("endpoint_versions_create", fields, "archive", zip_path)
        return http.post_json("endpoint_versions_create", fields)
    finally:
        if zip_path and zip_path != path and os.path.exists(zip_path):
            os.unlink(zip_path)


def download_version(http: SkillStoreHTTP, params: dict) -> dict:
    """Download a specific version of a skill."""
    slug = params.get("slug", "")
    version = params.get("version")
    if not slug:
        raise SkillStoreError("Parameter 'slug' is required")
    if version is None:
        raise SkillStoreError("Parameter 'version' is required")
    output_dir = params.get("output_dir", "/tmp")
    os.makedirs(output_dir, exist_ok=True)
    dest = http.download("endpoint_versions_download", {"slug": slug, "version": version}, output_dir)
    return {"downloaded": dest, "size": os.path.getsize(dest)}


# ---------- Comments ----------

def list_comments(http: SkillStoreHTTP, params: dict) -> Any:
    """List comments for a skill (optionally filtered by version)."""
    slug = params.get("slug", "")
    if not slug:
        raise SkillStoreError("Parameter 'slug' is required")
    query = {"slug": slug}
    if params.get("version") is not None:
        query["version"] = params["version"]
    return http.get("endpoint_comments_list", query)


def create_comment(http: SkillStoreHTTP, params: dict) -> Any:
    """Create a comment on a skill version with a 1-5 star rating."""
    slug = params.get("slug", "")
    version_number = params.get("version_number")
    author_login = params.get("author_login", "")
    text = params.get("text", "")
    rating = params.get("rating")

    if not slug:
        raise SkillStoreError("Parameter 'slug' is required")
    if version_number is None:
        raise SkillStoreError("Parameter 'version_number' is required")
    if not author_login:
        raise SkillStoreError("Parameter 'author_login' is required")
    if not text:
        raise SkillStoreError("Parameter 'text' is required")
    if rating is None:
        raise SkillStoreError("Parameter 'rating' is required (1-5)")
    rating = int(rating)
    if rating < 1 or rating > 5:
        raise SkillStoreError("Parameter 'rating' must be 1-5")

    data = {
        "slug": slug,
        "version_number": int(version_number),
        "author_login": author_login,
        "author_display": params.get("author_display", ""),
        "text": text,
        "rating": rating,
    }
    return http.post_json("endpoint_comments_create", data)


def delete_comment(http: SkillStoreHTTP, params: dict) -> Any:
    """Delete a comment by ID."""
    comment_id = params.get("comment_id")
    if comment_id is None:
        raise SkillStoreError("Parameter 'comment_id' is required")
    return http.post_json("endpoint_comments_delete", {"comment_id": int(comment_id)})


# ---------- Security ----------

def analyze_security(http: SkillStoreHTTP, params: dict) -> Any:
    """Run LLM security analysis on a skill version."""
    slug = params.get("slug", "")
    if not slug:
        raise SkillStoreError("Parameter 'slug' is required")
    version = params.get("version")
    if version is None:
        raise SkillStoreError("Parameter 'version' is required (version number)")
    return http.post_json("endpoint_versions_analyze", {
        "slug": slug,
        "version": int(version),
    })


# ---------- AI Search ----------

def ai_search_skills(http: SkillStoreHTTP, params: dict) -> Any:
    """AI-powered skill search by task/process description."""
    query = params.get("query", "")
    if not query or len(query.strip()) < 10:
        raise SkillStoreError("Parameter 'query' is required (min 10 chars)")
    return http.post_json("endpoint_skills_ai_search", {"query": query.strip()})


# ---------- Success Stories ----------

def publish_success_story(http: SkillStoreHTTP, params: dict) -> Any:
    """Publish a success story about using skills."""
    title = params.get("title", "")
    content = params.get("content", "")
    author_login = params.get("author_login", "")
    skill_slugs = params.get("skill_slugs", [])

    if not title:
        raise SkillStoreError("Parameter 'title' is required")
    if not content:
        raise SkillStoreError("Parameter 'content' is required")
    if not author_login:
        raise SkillStoreError("Parameter 'author_login' is required")
    if not skill_slugs or not isinstance(skill_slugs, list):
        raise SkillStoreError("Parameter 'skill_slugs' is required (list of slugs)")

    data: dict[str, Any] = {
        "title": title,
        "content": content,
        "author_login": author_login,
        "skill_slugs": skill_slugs,
    }
    if params.get("author_display"):
        data["author_display"] = params["author_display"]
    return http.post_json("endpoint_stories_create", data)


def list_success_stories(http: SkillStoreHTTP, params: dict) -> Any:
    """List success stories, optionally filtered by skill slug."""
    query: dict[str, Any] = {}
    if params.get("slug"):
        query["slug"] = params["slug"]
    if params.get("search"):
        query["search"] = params["search"]
    query["page"] = params.get("page", 1)
    query["per_page"] = params.get("per_page", 20)
    return http.get("endpoint_stories_list", query)


# ---------- Registry ----------

TOOLS: dict[str, tuple[callable, str]] = {
    "ListSkills": (list_skills, "List skills with optional filtering (search, category, tag, sort)"),
    "SearchSkills": (search_skills, "Search skills by text or regex pattern"),
    "GetSkill": (get_skill, "Get skill details by slug"),
    "CreateSkill": (create_skill, "Create new skill (auto-zips file/directory)"),
    "DeleteSkill": (delete_skill, "Delete skill by slug"),
    "MoveSkills": (move_skills, "Move skills to a different category"),
    "DownloadSkill": (download_skill, "Download skill archive file"),
    "SuggestCategory": (suggest_category, "AI-powered category suggestion"),
    "ListCategories": (list_categories, "Get full category tree"),
    "CreateCategory": (create_category, "Create a new category"),
    "UpdateCategory": (update_category, "Update category metadata"),
    "DeleteCategory": (delete_category, "Delete category with optional skill migration"),
    "GetStats": (get_stats, "Get catalog statistics"),
    "ListVersions": (list_versions, "List all versions of a skill"),
    "CreateVersion": (create_version, "Create new version (file optional, can update description/tags only)"),
    "DownloadVersion": (download_version, "Download a specific version of a skill"),
    "ListComments": (list_comments, "List comments for a skill (optionally by version)"),
    "CreateComment": (create_comment, "Create a comment with 1-5 star rating"),
    "DeleteComment": (delete_comment, "Delete a comment by ID"),
    "AiSearchSkills": (ai_search_skills, "AI-powered skill search by task/process description"),
    "AnalyzeSecurity": (analyze_security, "Run LLM security analysis on a skill version"),
    "PublishSuccessStory": (publish_success_story, "Publish a success story about using skills"),
    "ListSuccessStories": (list_success_stories, "List success stories (optionally by skill slug)"),
}


def list_tools() -> dict:
    """Print available tools."""
    return {
        "tools": [
            {"name": name, "description": desc}
            for name, (_, desc) in TOOLS.items()
        ]
    }


# ---------- Main ----------

def main() -> None:
    parser = argparse.ArgumentParser(description="SkillStore CLI tool")
    parser.add_argument("tool", help="Tool name (e.g. ListSkills, CreateSkill)")
    parser.add_argument("--params", default="{}", help="JSON params string")
    parser.add_argument("--params-file", help="Path to JSON params file")
    parser.add_argument("--print-tool-list", action="store_true", help="Print available tools and exit")
    args = parser.parse_args()

    if args.print_tool_list or args.tool == "ListTools":
        print(json.dumps(list_tools(), ensure_ascii=False, indent=2))
        return

    if args.tool not in TOOLS:
        print(json.dumps({"error": f"Unknown tool: {args.tool}", "available": list(TOOLS.keys())},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    # Parse params
    if args.params_file:
        with open(args.params_file, "r") as f:
            params = json.load(f)
    else:
        params = json.loads(args.params)

    # Init HTTP client
    base_url = os.environ.get("SKILLSTORE_BASE_URL", DEFAULT_BASE_URL)
    http = SkillStoreHTTP(base_url)

    # Execute tool
    func, _ = TOOLS[args.tool]
    try:
        result = func(http, params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except SkillStoreError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
