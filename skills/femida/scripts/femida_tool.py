#!/usr/bin/env python3
"""Femida tool runner with JSON params and stdlib-only HTTP client."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from collections import Counter
from typing import Any
from urllib import error, parse, request


class FemidaError(RuntimeError):
    pass


class FemidaHTTP:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        auth_scheme: str = "oauth",
        timeout: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.auth_scheme = auth_scheme.lower()
        self.timeout = timeout

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": self._format_auth_header(self.token),
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        }
        if extra:
            headers.update(extra)
        return headers

    def _format_auth_header(self, token: str) -> str:
        if self.auth_scheme == "bearer":
            return f"Bearer {token}"
        if self.auth_scheme == "oauth":
            return f"OAuth {token}"
        if token.startswith("t1."):
            return f"Bearer {token}"
        return f"OAuth {token}"

    def request_json(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        payload: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        url = self._make_url(path, query)
        req = request.Request(url=url, data=body, method=method.upper(), headers=self._headers(headers))
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                content_type = (resp.headers.get("Content-Type") or "").lower()
                if "application/json" in content_type:
                    return json.loads(raw.decode("utf-8"))
                try:
                    return json.loads(raw.decode("utf-8"))
                except Exception:
                    return {"raw": raw.decode("utf-8", errors="replace")}
        except error.HTTPError as e:
            raw = e.read() if e.fp else b""
            parsed: Any | None = None
            if raw:
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except Exception:
                    parsed = raw.decode("utf-8", errors="replace")
            raise FemidaError(f"HTTP {e.code} {method.upper()} {path}: {parsed if parsed is not None else e.reason}") from e
        except error.URLError as e:
            raise FemidaError(f"Network error for {method.upper()} {path}: {e}") from e

    def request_bytes(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        payload: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        url = self._make_url(path, query)
        req = request.Request(url=url, data=body, method=method.upper(), headers=self._headers(headers))
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read()
        except error.HTTPError as e:
            raw = e.read() if e.fp else b""
            text = raw.decode("utf-8", errors="replace") if raw else e.reason
            raise FemidaError(f"HTTP {e.code} {method.upper()} {path}: {text}") from e
        except error.URLError as e:
            raise FemidaError(f"Network error for {method.upper()} {path}: {e}") from e

    def _make_url(self, path: str, query: dict[str, Any] | None) -> str:
        path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{path}"
        if not query:
            return url
        pairs: list[tuple[str, str]] = []
        for key, value in query.items():
            if value is None:
                continue
            if isinstance(value, list):
                for item in value:
                    pairs.append((key, str(item)))
            else:
                pairs.append((key, str(value)))
        if pairs:
            url += "?" + parse.urlencode(pairs)
        return url


def _q(value: Any) -> str:
    return parse.quote(str(value), safe="")


def _load_params(params_raw: str | None, params_file: str | None) -> dict[str, Any]:
    if params_raw and params_file:
        raise FemidaError("Use only one of --params or --params-file")

    if params_file:
        with open(params_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise FemidaError("JSON from --params-file must be an object")
        return data

    if params_raw:
        data = json.loads(params_raw)
        if not isinstance(data, dict):
            raise FemidaError("JSON from --params must be an object")
        return data

    return {}


def _param_bool(params: dict[str, Any], key: str, default: bool = False) -> bool:
    if key not in params:
        return default
    value = params.get(key)
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)


def _param_int(params: dict[str, Any], key: str, default: int = 0, *, min_value: int | None = None) -> int:
    value = params.get(key, default)
    if value in [None, ""]:
        result = default
    else:
        try:
            result = int(value)
        except Exception as e:
            raise FemidaError(f"Param '{key}' must be an integer") from e
    if min_value is not None and result < min_value:
        raise FemidaError(f"Param '{key}' must be >= {min_value}")
    return result


def _extract_collection_values(response: Any) -> tuple[list[Any], str | None]:
    if isinstance(response, list):
        return response, None
    if isinstance(response, dict):
        for key in ["results", "values", "items", "data"]:
            value = response.get(key)
            if isinstance(value, list):
                return value, key
    return [], None


def _user_data(user: Any) -> Any:
    if not isinstance(user, dict):
        return user
    result: dict[str, Any] = {}
    for key in ["id", "username", "login", "firstname", "lastname", "fullname", "first_name", "last_name"]:
        if key in user and user[key] is not None:
            result[key] = user[key]
    return result or user


def _full_name(candidate: dict[str, Any]) -> str:
    parts = [
        str(candidate.get("first_name", "")).strip(),
        str(candidate.get("middle_name", "")).strip(),
        str(candidate.get("last_name", "")).strip(),
    ]
    full_name = " ".join(part for part in parts if part)
    if full_name:
        return full_name
    raw_full_name = candidate.get("full_name")
    return raw_full_name.strip() if isinstance(raw_full_name, str) else ""


def _candidate_url(candidate: dict[str, Any]) -> str | None:
    url = candidate.get("url")
    if isinstance(url, str) and url:
        return url
    candidate_id = candidate.get("id")
    if candidate_id is None:
        return None
    return f"https://femida.yandex-team.ru/candidates/{candidate_id}"


def _city_names(items: Any) -> list[str]:
    names: list[str] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                name = item.get("name") or item.get("name_ru") or item.get("name_en")
                if isinstance(name, str) and name:
                    names.append(name)
    return names


def _candidate_professions(items: Any) -> list[str]:
    names: list[str] = []
    if isinstance(items, list):
        for item in items:
            profession = item.get("profession") if isinstance(item, dict) else None
            if isinstance(profession, dict):
                name = profession.get("name")
                if isinstance(name, str) and name:
                    names.append(name)
    return names


def _skill_names(items: Any) -> list[str]:
    names: list[str] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name:
                    names.append(name)
    return names


def _contact_summary(items: Any) -> list[dict[str, Any]]:
    contacts: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            contacts.append(
                {
                    "id": item.get("id"),
                    "type": item.get("type"),
                    "account_id": item.get("account_id"),
                    "is_main": item.get("is_main"),
                    "is_active": item.get("is_active"),
                }
            )
    return contacts


def _attachments_summary(items: Any) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            attachments.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "created": item.get("created"),
                    "processed": item.get("processed"),
                }
            )
    return attachments


def _applications_summary(items: Any) -> list[dict[str, Any]]:
    applications: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            vacancy = item.get("vacancy") if isinstance(item.get("vacancy"), dict) else {}
            applications.append(
                {
                    "id": item.get("id"),
                    "status": item.get("status"),
                    "proposal_status": item.get("proposal_status"),
                    "resolution": item.get("resolution"),
                    "created": item.get("created"),
                    "modified": item.get("modified"),
                    "is_active": item.get("is_active"),
                    "is_archived": item.get("is_archived"),
                    "vacancy": {
                        "id": vacancy.get("id"),
                        "name": vacancy.get("name"),
                    },
                }
            )
    return applications


def _considerations_summary(items: Any) -> list[dict[str, Any]]:
    considerations: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            profession = item.get("profession") if isinstance(item.get("profession"), dict) else {}
            business_group = item.get("business_group") if isinstance(item.get("business_group"), dict) else {}
            business_unit = item.get("business_unit") if isinstance(item.get("business_unit"), dict) else {}
            considerations.append(
                {
                    "id": item.get("id"),
                    "status": item.get("status"),
                    "extended_status": item.get("extended_status"),
                    "resolution": item.get("resolution"),
                    "started": item.get("started"),
                    "finished": item.get("finished"),
                    "is_last": item.get("is_last"),
                    "profession": profession.get("name"),
                    "business_group": business_group.get("name"),
                    "business_unit": business_unit.get("name"),
                }
            )
    return considerations


def _jobs_summary(items: Any) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            jobs.append(
                {
                    "employer": item.get("employer"),
                    "position": item.get("position"),
                    "start_date": item.get("start_date"),
                    "end_date": item.get("end_date"),
                }
            )
    return jobs


def _educations_summary(items: Any) -> list[dict[str, Any]]:
    educations: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            educations.append(
                {
                    "institution": item.get("institution"),
                    "faculty": item.get("faculty"),
                    "degree": item.get("degree"),
                    "end_date": item.get("end_date"),
                }
            )
    return educations


def _interviews_summary(items: Any) -> list[dict[str, Any]]:
    interviews: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            interviews.append(
                {
                    "id": item.get("id"),
                    "type": item.get("type"),
                    "state": item.get("state"),
                    "section": item.get("section"),
                    "name": item.get("name"),
                    "grade": item.get("grade"),
                    "grade_verbose": item.get("grade_verbose"),
                    "resolution": item.get("resolution"),
                    "finished": item.get("finished"),
                    "interviewer": _user_data(item.get("interviewer")),
                }
            )
    return interviews


def _candidate_search_summary(candidate: dict[str, Any], *, include_passages: bool = False) -> dict[str, Any]:
    last_job = candidate.get("last_job") if isinstance(candidate.get("last_job"), dict) else {}
    result = {
        "id": candidate.get("id"),
        "full_name": _full_name(candidate),
        "city": candidate.get("city"),
        "country": candidate.get("country"),
        "status": candidate.get("status"),
        "extended_status": candidate.get("extended_status"),
        "is_available": candidate.get("is_available"),
        "is_current_employee": candidate.get("is_current_employee"),
        "main_recruiter": _user_data(candidate.get("main_recruiter")),
        "professions": [item.get("name") for item in candidate.get("professions", []) if isinstance(item, dict) and item.get("name")],
        "skills": _skill_names(candidate.get("skills")),
        "last_job": {
            "employer": last_job.get("employer"),
            "position": last_job.get("position"),
        },
        "modified": candidate.get("modified"),
        "created": candidate.get("created"),
        "url": _candidate_url(candidate),
    }
    if include_passages:
        result["passages"] = candidate.get("passages", [])
    return result


def _candidate_compact(candidate: dict[str, Any], *, include_contacts: bool = False) -> dict[str, Any]:
    result = {
        "id": candidate.get("id"),
        "full_name": _full_name(candidate),
        "birthday": candidate.get("birthday"),
        "gender": candidate.get("gender"),
        "country": candidate.get("country"),
        "city": candidate.get("city"),
        "target_cities": _city_names(candidate.get("target_cities")),
        "status": candidate.get("status"),
        "extended_status": candidate.get("extended_status"),
        "created": candidate.get("created"),
        "modified": candidate.get("modified"),
        "is_current_employee": candidate.get("is_current_employee"),
        "main_recruiter": _user_data(candidate.get("main_recruiter")),
        "recruiters": [_user_data(item) for item in candidate.get("recruiters", []) if isinstance(item, dict)],
        "candidate_professions": _candidate_professions(candidate.get("candidate_professions")),
        "skills": _skill_names(candidate.get("skills")),
        "tags": candidate.get("tags", []),
        "attachments": _attachments_summary(candidate.get("attachments")),
        "applications": _applications_summary(candidate.get("applications")),
        "considerations": _considerations_summary(candidate.get("considerations")),
        "jobs": _jobs_summary(candidate.get("jobs")),
        "educations": _educations_summary(candidate.get("educations")),
        "interviews": _interviews_summary(candidate.get("interviews")),
        "counts": candidate.get("counts"),
        "cv_update_date": candidate.get("cv_update_date"),
        "hire_interviews_count": candidate.get("hire_interviews_count"),
        "nohire_interviews_count": candidate.get("nohire_interviews_count"),
        "skype_interviews_count": candidate.get("skype_interviews_count"),
        "on_site_interviews_count": candidate.get("on_site_interviews_count"),
        "url": _candidate_url(candidate),
    }
    contacts = _contact_summary(candidate.get("contacts"))
    if include_contacts:
        result["contacts"] = contacts
    elif contacts:
        result["contacts_hidden"] = len(contacts)
    return result


def _compact_collection_response(response: Any, *, limit: int | None = None) -> Any:
    values, key = _extract_collection_values(response)
    if not values and key is None:
        return response

    total = len(values)
    if limit is not None and limit > 0:
        values = values[:limit]

    if isinstance(response, dict):
        result = dict(response)
        target_key = key or "items"
        result[target_key] = values
        result["returned"] = len(values)
        if "count" not in result:
            result["count"] = total
        return result

    return {
        "count": total,
        "returned": len(values),
        "items": values,
    }


def _search_results(response: Any) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    results = response.get("results")
    if not isinstance(results, list):
        return []
    return [item for item in results if isinstance(item, dict)]


def _dedupe_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[Any] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        candidate_id = item.get("id")
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        deduped.append(item)
    return deduped


def _active_application_slots(candidate: dict[str, Any]) -> int:
    count = 0
    for application in candidate.get("applications", []):
        if not isinstance(application, dict):
            continue
        if application.get("is_active"):
            count += 1
            continue
        status = application.get("status")
        if status and status not in {"closed", "archived"}:
            count += 1
    return count


def _latest_application(candidate: dict[str, Any]) -> dict[str, Any] | None:
    applications = [item for item in candidate.get("applications", []) if isinstance(item, dict)]
    if not applications:
        return None
    return max(
        applications,
        key=lambda item: (
            str(item.get("modified") or item.get("created") or ""),
            int(item.get("id") or 0),
        ),
    )


def _last_consideration(candidate: dict[str, Any]) -> dict[str, Any] | None:
    considerations = [item for item in candidate.get("considerations", []) if isinstance(item, dict)]
    if not considerations:
        return None
    for item in considerations:
        if item.get("is_last"):
            return item
    return max(
        considerations,
        key=lambda item: (
            str(item.get("finished") or item.get("started") or ""),
            int(item.get("id") or 0),
        ),
    )


def _counter_dict(counter: Counter[Any]) -> dict[str, int]:
    return {str(key): value for key, value in counter.most_common()}


def _section_row(candidate: dict[str, Any]) -> dict[str, Any]:
    hire_sections = int(candidate.get("hire_interviews_count") or 0)
    nohire_sections = int(candidate.get("nohire_interviews_count") or 0)
    skype_interviews = int(candidate.get("skype_interviews_count") or 0)
    onsite_interviews = int(candidate.get("on_site_interviews_count") or 0)
    return {
        "id": candidate.get("id"),
        "full_name": _full_name(candidate),
        "status": candidate.get("status"),
        "extended_status": candidate.get("extended_status"),
        "url": _candidate_url(candidate),
        "hire_sections": hire_sections,
        "nohire_sections": nohire_sections,
        "skype_interviews": skype_interviews,
        "onsite_interviews": onsite_interviews,
        "decision_sections": hire_sections + nohire_sections,
        "all_interviews": skype_interviews + onsite_interviews,
    }


def _section_sort_key(row: dict[str, Any], sort_by: str) -> tuple[Any, ...]:
    hire_sections = int(row.get("hire_sections") or 0)
    nohire_sections = int(row.get("nohire_sections") or 0)
    all_interviews = int(row.get("all_interviews") or 0)
    status = row.get("status")

    if sort_by in {"net", "net_hire"}:
        return (-(hire_sections - nohire_sections), -hire_sections, nohire_sections, -all_interviews, 0 if status == "in_progress" else 1, int(row.get("id") or 0))
    if sort_by == "ratio":
        ratio = 0.0 if hire_sections <= 0 else hire_sections / max(nohire_sections, 1)
        return (-ratio, -hire_sections, nohire_sections, -all_interviews, 0 if status == "in_progress" else 1, int(row.get("id") or 0))
    return (-hire_sections, nohire_sections, -all_interviews, 0 if status == "in_progress" else 1, int(row.get("id") or 0))


def _load_token_from_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            token = fh.read().strip()
    except OSError as e:
        raise FemidaError(f"Failed to read token file '{path}': {e}") from e
    if not token:
        raise FemidaError(f"Token file '{path}' is empty")
    return token


def _resolve_token() -> str:
    token = os.getenv("FEMIDA_TOKEN", "").strip()
    if token:
        return token
    token_file = os.getenv("FEMIDA_TOKEN_FILE", "").strip()
    if token_file:
        return _load_token_from_file(token_file)
    raise FemidaError("Missing FEMIDA_TOKEN or FEMIDA_TOKEN_FILE")


class FemidaTools:
    def __init__(self, http: FemidaHTTP):
        self.http = http

    def run(self, tool_name: str, params: dict[str, Any]) -> Any:
        tools = {
            "SearchCandidate": self.search_candidate,
            "CountCandidates": self.count_candidates,
            "SummarizeFunnel": self.summarize_funnel,
            "SummarizeSections": self.summarize_sections,
            "TopCandidatesBySections": self.top_candidates_by_sections,
            "GetCandidate": self.get_candidate,
            "GetCandidateNotes": self.get_candidate_notes,
            "GetCandidateSalaryCosts": self.get_candidate_salary_costs,
            "GetCandidateDismissedFeedback": self.get_candidate_dismissed_feedback,
            "GetCandidateMessages": self.get_candidate_messages,
            "GetCandidateOffers": self.get_candidate_offers,
            "GetInterview": self.get_interview,
            "DownloadAttachment": self.download_attachment,
            "search-candidate": self.search_candidate,
            "count-candidates": self.count_candidates,
            "summarize-funnel": self.summarize_funnel,
            "summarize-sections": self.summarize_sections,
            "top-candidates-by-sections": self.top_candidates_by_sections,
            "candidate-info": self.get_candidate,
            "candidate-notes": self.get_candidate_notes,
            "candidate-salary-costs": self.get_candidate_salary_costs,
            "candidate-dismissed-feedback": self.get_candidate_dismissed_feedback,
            "candidate-messages": self.get_candidate_messages,
            "candidate-offers": self.get_candidate_offers,
            "interview-info": self.get_interview,
            "download-attachment": self.download_attachment,
        }
        handler = tools.get(tool_name)
        if handler is None:
            supported = ", ".join(self.tool_names())
            raise FemidaError(f"Unknown tool '{tool_name}'. Supported: {supported}")
        return handler(params)

    @staticmethod
    def tool_names() -> list[str]:
        return [
            "SearchCandidate",
            "CountCandidates",
            "SummarizeFunnel",
            "SummarizeSections",
            "TopCandidatesBySections",
            "GetCandidate",
            "GetCandidateNotes",
            "GetCandidateSalaryCosts",
            "GetCandidateDismissedFeedback",
            "GetCandidateMessages",
            "GetCandidateOffers",
            "GetInterview",
            "DownloadAttachment",
        ]

    def _search_page(self, text: str, *, page: int = 1) -> Any:
        query = {"page": page} if page > 1 else None
        return self.http.request_json("POST", "/candidates/search/v2", query=query, payload={"text": text})

    def _fetch_search_pages(self, text: str, *, page: int = 1, all_pages: bool = False, max_pages: int = 0) -> tuple[list[dict[str, Any]], bool]:
        response = self._search_page(text, page=page)
        if not isinstance(response, dict):
            raise FemidaError("Unexpected search response format")

        responses = [response]
        if not all_pages:
            return responses, False

        current_page = page
        pages_fetched = 1
        results_seen = len(_search_results(response))
        total_matches = response.get("count") if isinstance(response.get("count"), int) else None
        truncated = False

        while response.get("next"):
            if max_pages > 0 and pages_fetched >= max_pages:
                truncated = True
                break
            if total_matches is not None and results_seen >= total_matches:
                break
            current_page += 1
            response = self._search_page(text, page=current_page)
            if not isinstance(response, dict):
                break
            responses.append(response)
            pages_fetched += 1
            page_results = _search_results(response)
            results_seen += len(page_results)
            if not page_results:
                break

        return responses, truncated

    def _prepare_search_dataset(
        self,
        params: dict[str, Any],
        *,
        default_all_pages: bool,
        default_dedupe: bool,
    ) -> dict[str, Any]:
        if "text" not in params or params.get("text") is None:
            raise FemidaError("Missing required param: text")

        text = str(params.get("text"))
        page = _param_int(params, "page", 1, min_value=1)
        all_pages = _param_bool(params, "all_pages", default_all_pages)
        max_pages = _param_int(params, "max_pages", 0, min_value=0)
        dedupe = _param_bool(params, "dedupe", default_dedupe)
        only_available = _param_bool(params, "only_available", False)

        responses, truncated = self._fetch_search_pages(text, page=page, all_pages=all_pages, max_pages=max_pages)
        raw_items: list[dict[str, Any]] = []
        for response in responses:
            raw_items.extend(_search_results(response))

        filtered_items = raw_items
        if only_available:
            filtered_items = [item for item in filtered_items if item.get("is_available")]

        duplicates_removed = 0
        if dedupe:
            deduped_items = _dedupe_candidates(filtered_items)
            duplicates_removed = len(filtered_items) - len(deduped_items)
            filtered_items = deduped_items

        first_response = responses[0]
        notes: list[str] = []
        if only_available and not all_pages:
            notes.append("`only_available` applies only to the fetched page; use `all_pages=true` for query-wide counts.")
        if truncated:
            notes.append("Reached `max_pages` before exhausting search results; counts and analytics are partial.")
        if dedupe and duplicates_removed > 0:
            notes.append(f"Removed {duplicates_removed} duplicate candidates by id.")

        return {
            "query": text,
            "page": page,
            "all_pages": all_pages,
            "max_pages": max_pages if max_pages > 0 else None,
            "dedupe": dedupe,
            "only_available": only_available,
            "responses": responses,
            "first_response": first_response,
            "items": filtered_items,
            "raw_items": raw_items,
            "pages_fetched": len(responses),
            "fetched_results": len(raw_items),
            "duplicates_removed": duplicates_removed,
            "total_matches": first_response.get("count") if isinstance(first_response, dict) else None,
            "next": first_response.get("next") if isinstance(first_response, dict) else None,
            "previous": first_response.get("previous") if isinstance(first_response, dict) else None,
            "meta": first_response.get("meta") if isinstance(first_response.get("meta"), dict) else None,
            "truncated": truncated,
            "notes": notes,
        }

    def search_candidate(self, params: dict[str, Any]) -> Any:
        if "text" not in params or params.get("text") is None:
            raise FemidaError("Missing required param: text")

        text = str(params.get("text"))
        page = _param_int(params, "page", 1, min_value=1)
        if _param_bool(params, "raw", False):
            return self._search_page(text, page=page)

        dataset = self._prepare_search_dataset(params, default_all_pages=False, default_dedupe=False)
        include_passages = _param_bool(params, "include_passages", False)
        limit = _param_int(params, "limit", 0, min_value=0)

        items = dataset["items"]
        if limit > 0:
            items = items[:limit]

        output: dict[str, Any] = {
            "query": dataset["query"],
            "page": dataset["page"],
            "all_pages": dataset["all_pages"],
            "pages_fetched": dataset["pages_fetched"],
            "total_matches": dataset["total_matches"],
            "fetched_results": dataset["fetched_results"],
            "duplicates_removed": dataset["duplicates_removed"],
            "next": dataset["next"],
            "previous": dataset["previous"],
            "returned_results": len(items),
            "results": [_candidate_search_summary(item, include_passages=include_passages) for item in items],
        }
        if dataset["meta"] is not None:
            output["meta"] = dataset["meta"]
        if dataset["notes"]:
            output["notes"] = dataset["notes"]
        return output

    def count_candidates(self, params: dict[str, Any]) -> Any:
        dataset = self._prepare_search_dataset(params, default_all_pages=True, default_dedupe=True)
        items = dataset["items"]

        available_candidates = sum(1 for item in items if item.get("is_available"))
        in_progress_candidates = sum(1 for item in items if item.get("status") == "in_progress")
        candidates_with_active_applications = sum(1 for item in items if _active_application_slots(item) > 0)

        output: dict[str, Any] = {
            "query": dataset["query"],
            "all_pages": dataset["all_pages"],
            "pages_fetched": dataset["pages_fetched"],
            "total_matches": dataset["total_matches"],
            "unique_candidates": len(items),
            "fetched_results": dataset["fetched_results"],
            "duplicates_removed": dataset["duplicates_removed"],
            "exact": dataset["all_pages"] and not dataset["truncated"],
            "active_candidates": {
                "available": available_candidates,
                "in_progress": in_progress_candidates,
                "with_active_applications": candidates_with_active_applications,
            },
            "definitions": {
                "available": "Candidates with `is_available=true` in search results.",
                "in_progress": "Candidates with `status=in_progress`.",
                "with_active_applications": "Candidates with at least one active application.",
            },
        }
        if dataset["notes"]:
            output["notes"] = dataset["notes"]
        return output

    def summarize_funnel(self, params: dict[str, Any]) -> Any:
        dataset = self._prepare_search_dataset(params, default_all_pages=True, default_dedupe=True)
        items = dataset["items"]
        sample_limit = _param_int(params, "limit", 5, min_value=0)

        status_counts = Counter(item.get("status") or "unknown" for item in items)
        extended_status_counts = Counter(item.get("extended_status") or "unknown" for item in items)
        current_stage_counts = Counter((item.get("extended_status") or item.get("status") or "unknown") for item in items if item.get("status") == "in_progress")
        active_application_slots = Counter(_active_application_slots(item) for item in items)
        last_consideration_resolutions = Counter()
        latest_application_outcomes = Counter()

        for item in items:
            last_consideration = _last_consideration(item)
            if last_consideration is not None:
                resolution = last_consideration.get("resolution") or "open"
                last_consideration_resolutions[resolution] += 1

            latest_application = _latest_application(item)
            if latest_application is not None:
                status = latest_application.get("status") or "unknown"
                resolution = latest_application.get("resolution") or ""
                latest_application_outcomes[f"{status}/{resolution}"] += 1

        current_candidates = [
            _candidate_search_summary(item)
            for item in items
            if item.get("status") == "in_progress"
        ]
        if sample_limit > 0:
            current_candidates = current_candidates[:sample_limit]

        output: dict[str, Any] = {
            "query": dataset["query"],
            "all_pages": dataset["all_pages"],
            "pages_fetched": dataset["pages_fetched"],
            "total_matches": dataset["total_matches"],
            "unique_candidates": len(items),
            "exact": dataset["all_pages"] and not dataset["truncated"],
            "status_counts": _counter_dict(status_counts),
            "extended_status_counts": _counter_dict(extended_status_counts),
            "current_stage_counts": _counter_dict(current_stage_counts),
            "active_candidates": {
                "available": sum(1 for item in items if item.get("is_available")),
                "in_progress": sum(1 for item in items if item.get("status") == "in_progress"),
                "with_active_applications": sum(1 for item in items if _active_application_slots(item) > 0),
            },
            "active_application_slots_per_candidate": {str(key): value for key, value in sorted(active_application_slots.items())},
            "last_consideration_resolutions": _counter_dict(last_consideration_resolutions),
            "latest_application_outcomes": _counter_dict(latest_application_outcomes),
            "current_candidates_sample": current_candidates,
        }
        if dataset["notes"]:
            output["notes"] = dataset["notes"]
        return output

    def summarize_sections(self, params: dict[str, Any]) -> Any:
        dataset = self._prepare_search_dataset(params, default_all_pages=True, default_dedupe=True)
        limit = _param_int(params, "limit", 5, min_value=0)
        rows = [_section_row(item) for item in dataset["items"]]

        candidates_with_any_interview = [row for row in rows if row["all_interviews"] > 0]
        candidates_with_decision_sections = [row for row in rows if row["decision_sections"] > 0]
        candidates_only_hire = [row for row in candidates_with_decision_sections if row["hire_sections"] > 0 and row["nohire_sections"] == 0]
        candidates_only_nohire = [row for row in candidates_with_decision_sections if row["nohire_sections"] > 0 and row["hire_sections"] == 0]
        candidates_mixed = [row for row in candidates_with_decision_sections if row["hire_sections"] > 0 and row["nohire_sections"] > 0]
        current_rows = [row for row in rows if row["status"] == "in_progress"]

        top_passed = sorted([row for row in rows if row["hire_sections"] > 0], key=lambda row: _section_sort_key(row, "hire"))
        top_failed = sorted([row for row in rows if row["nohire_sections"] > 0], key=lambda row: (-row["nohire_sections"], row["hire_sections"], -row["all_interviews"], 0 if row["status"] == "in_progress" else 1, int(row["id"] or 0)))

        if limit > 0:
            top_passed = top_passed[:limit]
            top_failed = top_failed[:limit]

        output: dict[str, Any] = {
            "query": dataset["query"],
            "all_pages": dataset["all_pages"],
            "pages_fetched": dataset["pages_fetched"],
            "total_matches": dataset["total_matches"],
            "unique_candidates": len(rows),
            "exact": dataset["all_pages"] and not dataset["truncated"],
            "candidates_with_any_interview": len(candidates_with_any_interview),
            "candidates_with_decision_sections": len(candidates_with_decision_sections),
            "candidates_only_hire_sections": len(candidates_only_hire),
            "candidates_only_nohire_sections": len(candidates_only_nohire),
            "candidates_mixed_hire_nohire_sections": len(candidates_mixed),
            "total_hire_sections": sum(row["hire_sections"] for row in rows),
            "total_nohire_sections": sum(row["nohire_sections"] for row in rows),
            "total_skype_interviews": sum(row["skype_interviews"] for row in rows),
            "total_onsite_interviews": sum(row["onsite_interviews"] for row in rows),
            "decision_sections_per_candidate_distribution": {str(key): value for key, value in sorted(Counter(row["decision_sections"] for row in candidates_with_decision_sections).items())},
            "all_interviews_per_candidate_distribution": {str(key): value for key, value in sorted(Counter(row["all_interviews"] for row in candidates_with_any_interview).items())},
            "current_in_progress": len(current_rows),
            "current_in_progress_with_any_section_signal": sum(1 for row in current_rows if row["decision_sections"] > 0 or row["all_interviews"] > 0),
            "current_in_progress_section_breakdown": {
                "hire_sections": sum(row["hire_sections"] for row in current_rows),
                "nohire_sections": sum(row["nohire_sections"] for row in current_rows),
                "skype_interviews": sum(row["skype_interviews"] for row in current_rows),
                "onsite_interviews": sum(row["onsite_interviews"] for row in current_rows),
            },
            "top_passed_candidates": top_passed,
            "top_failed_candidates": top_failed,
        }
        if dataset["notes"]:
            output["notes"] = dataset["notes"]
        return output

    def top_candidates_by_sections(self, params: dict[str, Any]) -> Any:
        dataset = self._prepare_search_dataset(params, default_all_pages=True, default_dedupe=True)
        rows = [_section_row(item) for item in dataset["items"]]

        limit = _param_int(params, "limit", 10, min_value=0)
        min_hire = _param_int(params, "min_hire", 0, min_value=0)
        status_filter = params.get("status")
        extended_status_filter = params.get("extended_status")
        sort_by = str(params.get("sort_by") or "hire")

        filtered_rows = []
        for row in rows:
            if status_filter and row["status"] != status_filter:
                continue
            if extended_status_filter and row["extended_status"] != extended_status_filter:
                continue
            if row["hire_sections"] < min_hire:
                continue
            filtered_rows.append(row)

        filtered_rows = sorted(filtered_rows, key=lambda row: _section_sort_key(row, sort_by))
        if limit > 0:
            filtered_rows = filtered_rows[:limit]

        output: dict[str, Any] = {
            "query": dataset["query"],
            "all_pages": dataset["all_pages"],
            "pages_fetched": dataset["pages_fetched"],
            "total_matches": dataset["total_matches"],
            "unique_candidates": len(rows),
            "exact": dataset["all_pages"] and not dataset["truncated"],
            "filters": {
                "status": status_filter,
                "extended_status": extended_status_filter,
                "min_hire": min_hire,
                "sort_by": sort_by,
            },
            "returned_candidates": len(filtered_rows),
            "candidates": filtered_rows,
        }
        if dataset["notes"]:
            output["notes"] = dataset["notes"]
        return output

    def get_candidate(self, params: dict[str, Any]) -> Any:
        candidate_id = params.get("id", params.get("candidate_id"))
        if candidate_id is None:
            raise FemidaError("Missing required param: id")
        response = self.http.request_json("GET", f"/candidates/{_q(candidate_id)}")
        if _param_bool(params, "raw", False):
            return response
        if not isinstance(response, dict):
            return response
        return _candidate_compact(response, include_contacts=_param_bool(params, "include_contacts", False))

    def get_candidate_notes(self, params: dict[str, Any]) -> Any:
        return self._get_candidate_subresource(params, "notes")

    def get_candidate_salary_costs(self, params: dict[str, Any]) -> Any:
        return self._get_candidate_subresource(params, "salary_costs")

    def get_candidate_dismissed_feedback(self, params: dict[str, Any]) -> Any:
        return self._get_candidate_subresource(params, "dismissed_feedback")

    def get_candidate_messages(self, params: dict[str, Any]) -> Any:
        return self._get_candidate_subresource(params, "messages")

    def get_candidate_offers(self, params: dict[str, Any]) -> Any:
        return self._get_candidate_subresource(params, "offers")

    def get_interview(self, params: dict[str, Any]) -> Any:
        interview_id = params.get("id", params.get("interview_id"))
        if interview_id is None:
            raise FemidaError("Missing required param: id")
        response = self.http.request_json("GET", f"/interviews/{_q(interview_id)}")
        if _param_bool(params, "raw", False):
            return response
        if not isinstance(response, dict):
            return response
        return {
            "id": response.get("id"),
            "type": response.get("type"),
            "state": response.get("state"),
            "name": response.get("name"),
            "section": response.get("section"),
            "grade": response.get("grade"),
            "grade_verbose": response.get("grade_verbose"),
            "resolution": response.get("resolution"),
            "finished": response.get("finished"),
            "interviewer": _user_data(response.get("interviewer")),
            "candidate": _user_data(response.get("candidate")),
        }

    def download_attachment(self, params: dict[str, Any]) -> Any:
        attachment_id = params.get("id", params.get("attachment_id"))
        if attachment_id is None:
            raise FemidaError("Missing required param: id")
        raw = self.http.request_bytes("GET", f"/attachments/{_q(attachment_id)}")
        return {
            "attachment_id": attachment_id,
            "encoding": "base64",
            "size": len(raw),
            "content": base64.b64encode(raw).decode("ascii"),
        }

    def _get_candidate_subresource(self, params: dict[str, Any], resource: str) -> Any:
        candidate_id = params.get("id", params.get("candidate_id"))
        if candidate_id is None:
            raise FemidaError("Missing required param: id")
        response = self.http.request_json("GET", f"/candidates/{_q(candidate_id)}/{resource}")
        if _param_bool(params, "raw", False):
            return response
        limit = _param_int(params, "limit", 0, min_value=0)
        return _compact_collection_response(response, limit=limit if limit > 0 else None)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Femida operations with a stdlib-only implementation.",
    )
    parser.add_argument("tool", help="Tool name, e.g. SearchCandidate, GetCandidate")
    parser.add_argument("--params", help="JSON object with tool params")
    parser.add_argument("--params-file", help="Path to JSON file with tool params")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds")
    parser.add_argument(
        "--auth-scheme",
        choices=["oauth", "bearer", "auto"],
        help="Authorization scheme. Defaults to FEMIDA_AUTH_SCHEME or oauth.",
    )
    parser.add_argument(
        "--print-tool-list",
        action="store_true",
        help="Print supported tool names and exit",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if args.print_tool_list:
        print(json.dumps(FemidaTools.tool_names(), ensure_ascii=False, indent=2))
        return 0

    base_url = os.getenv("FEMIDA_BASE_URL", "https://femida.yandex-team.ru/api")
    auth_scheme = args.auth_scheme or os.getenv("FEMIDA_AUTH_SCHEME", "oauth")

    try:
        token = _resolve_token()
        params = _load_params(args.params, args.params_file)
        http = FemidaHTTP(
            base_url=base_url,
            token=token,
            auth_scheme=auth_scheme,
            timeout=max(args.timeout, 1),
        )
        tools = FemidaTools(http)
        result = tools.run(args.tool, params)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except FemidaError as e:
        print(
            json.dumps(
                {
                    "error": str(e),
                    "hint": "Set FEMIDA_TOKEN or FEMIDA_TOKEN_FILE before running the tool.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
