import json

import requests


class LLMError(Exception):
    """Raised when Groq cannot produce a valid test plan."""


def _extract_json(content: str) -> dict:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").removeprefix("json").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMError("Groq returned a response that was not valid JSON.") from exc


def generate_test_plan(source: dict, api_key: str, model: str) -> dict:
    if not api_key:
        raise LLMError("Groq API key is missing. Add it in Settings.")

    system_prompt = (
        "You are a senior QA engineer. Generate a grounded test plan from the supplied Jira source. "
        "Use only the source evidence. Never invent requirements, behavior, test data, or expected results. "
        "When evidence is missing, write a gap instead. Return JSON only matching the requested schema."
    )
    user_prompt = f"""Create a test plan for this normalized Jira source.

Required JSON shape:
{{
  "issueKey": "string",
  "title": "string",
  "scope": {{"inScope": ["string"], "outOfScope": ["string"], "assumptions": ["string"]}},
  "testCases": [{{"id": "TC-001", "title": "string", "type": "functional|negative|boundary|exploratory", "priority": "high|medium|low|not specified", "preconditions": ["string"], "steps": [{{"action": "string", "expectedResult": "string"}}], "sourceEvidence": ["string"], "coverage": "direct|inferred|blocked"}}],
  "gaps": ["string"],
  "validation": {{"isGrounded": true, "missingEvidence": ["string"], "warnings": ["string"]}}
}}

Source:
{json.dumps(source, indent=2)}"""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model or "openai/gpt-oss-120b",
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=120,
        )
    except requests.RequestException as exc:
        raise LLMError(f"Could not reach Groq: {exc}") from exc

    if response.status_code in (401, 403):
        raise LLMError("Groq authentication failed. Check the API key.")
    if response.status_code == 429:
        raise LLMError("Groq rate limit reached. Try again shortly.")
    if response.status_code != 200:
        raise LLMError(f"Groq request failed with HTTP {response.status_code}.")

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMError("Groq returned an unexpected response shape.") from exc
    return validate_test_plan(_extract_json(content))


def validate_test_plan(plan: dict) -> dict:
    required = {"issueKey", "title", "scope", "testCases", "gaps", "validation"}
    missing = required - set(plan)
    if missing:
        raise LLMError(f"Generated test plan is missing fields: {', '.join(sorted(missing))}.")
    if not isinstance(plan["testCases"], list):
        raise LLMError("Generated test plan testCases must be a list.")
    for case in plan["testCases"]:
        for key in ("id", "title", "steps", "sourceEvidence", "coverage"):
            if key not in case:
                raise LLMError(f"Generated test case is missing '{key}'.")
    return plan


def check_connection(api_key: str, model: str) -> str:
    if not api_key:
        raise LLMError("Groq API key is missing.")
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model or "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "Reply with OK."}], "max_tokens": 8, "temperature": 0},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise LLMError(f"Could not reach Groq: {exc}") from exc
    if response.status_code in (401, 403):
        raise LLMError("Groq authentication failed. Check the API key.")
    if response.status_code != 200:
        raise LLMError(f"Groq connection test failed with HTTP {response.status_code}.")
    return response.json()["choices"][0]["message"]["content"].strip()
