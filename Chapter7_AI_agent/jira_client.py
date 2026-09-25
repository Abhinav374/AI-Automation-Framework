import re
from datetime import datetime, timezone

import requests


ISSUE_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]*-\d+\b")


class JiraError(Exception):
    """Raised when Jira cannot return a usable issue."""


def extract_issue_key(text: str) -> str | None:
    match = ISSUE_KEY_RE.search(text.upper())
    return match.group(0) if match else None


def _clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        chunks = []
        for node in value.get("content", []):
            if node.get("type") == "text":
                chunks.append(node.get("text", ""))
            chunks.extend(_clean_text(child) for child in node.get("content", []))
        return " ".join(chunk for chunk in chunks if chunk).strip()
    if isinstance(value, list):
        return " ".join(_clean_text(item) for item in value if item).strip()
    return str(value).strip()


def fetch_issue(base_url: str, email: str, api_token: str, issue_key: str, acceptance_field: str = "") -> dict:
    if not base_url or not email or not api_token:
        raise JiraError("Jira settings are incomplete. Add the URL, email, and API token in Settings.")
    if not ISSUE_KEY_RE.fullmatch(issue_key.upper().strip()):
        raise JiraError("Enter a valid Jira issue key such as PROJ-123.")

    fields = "summary,description,issuetype,status,priority,labels,components,comment"
    if acceptance_field and acceptance_field not in fields.split(","):
        fields = f"{fields},{acceptance_field}"
    url = f"{base_url.rstrip('/')}/rest/api/3/issue/{issue_key.strip().upper()}"

    try:
        response = requests.get(
            url,
            auth=(email, api_token),
            params={"fields": fields},
            headers={"Accept": "application/json"},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise JiraError(f"Could not reach Jira: {exc}") from exc

    if response.status_code == 401:
        raise JiraError("Jira authentication failed. Check the email and API token.")
    if response.status_code == 403:
        raise JiraError("Jira denied access to this issue. Check the token permissions.")
    if response.status_code == 404:
        raise JiraError(f"Issue {issue_key.upper()} was not found or is not visible to this account.")
    if response.status_code != 200:
        raise JiraError(f"Jira request failed with HTTP {response.status_code}.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise JiraError("Jira returned an invalid JSON response.") from exc

    raw_fields = payload.get("fields", {})
    acceptance_value = raw_fields.get(acceptance_field) if acceptance_field else None
    comments = []
    for comment in raw_fields.get("comment", {}).get("comments", []):
        body = _clean_text(comment.get("body"))
        if body:
            comments.append(body)

    return {
        "issueKey": issue_key.upper().strip(),
        "source": {
            "jiraBaseUrl": base_url.rstrip("/"),
            "retrievedAt": datetime.now(timezone.utc).isoformat(),
            "fields": {
                "summary": _clean_text(raw_fields.get("summary")),
                "description": _clean_text(raw_fields.get("description")),
                "acceptanceCriteria": _clean_text(acceptance_value),
                "issueType": _clean_text(raw_fields.get("issuetype", {}).get("name")),
                "status": _clean_text(raw_fields.get("status", {}).get("name")),
                "priority": _clean_text(raw_fields.get("priority", {}).get("name")),
                "labels": raw_fields.get("labels", []),
                "components": [item.get("name", "") for item in raw_fields.get("components", [])],
                "comments": comments,
            },
        },
        "evidence": [
            {"sourcePath": "fields.summary", "valuePresent": bool(_clean_text(raw_fields.get("summary")))},
            {"sourcePath": "fields.description", "valuePresent": bool(_clean_text(raw_fields.get("description")))},
            {"sourcePath": acceptance_field or "acceptanceCriteria", "valuePresent": bool(_clean_text(acceptance_value))},
        ],
        "missingFields": [
            field for field, value in {
                "summary": _clean_text(raw_fields.get("summary")),
                "description": _clean_text(raw_fields.get("description")),
                "acceptanceCriteria": _clean_text(acceptance_value),
            }.items() if not value
        ],
        "warnings": ["Acceptance criteria field is not configured."] if not acceptance_field else [],
    }


def check_connection(base_url: str, email: str, api_token: str, issue_key: str) -> dict:
    return fetch_issue(base_url, email, api_token, issue_key)
