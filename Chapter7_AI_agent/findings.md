# Findings - Jira Test Plan Creator

## Scope and Evidence

These findings began with the repository's `BLAST.md`, `Prompt_Used.md`, and `ANIT-HALLUCINATION.md` as of 2026-09-04. The user subsequently approved a local Streamlit UI, Jira REST retrieval, and Groq as the LLM provider. No live Jira response or credentials were available during implementation.

## Verified Findings

- `BLAST.md` requires Protocol 0 initialization before scripts or tools are written.
- Protocol 0 requires project memory for a task plan, findings, progress, and a project constitution containing schemas, behavioral rules, and architectural invariants.
- The requested objective is a test plan creator driven by a Jira ID.
- The repository's anti-hallucination rules require facts to be traceable to supplied input and require missing information to be identified rather than invented.
- There is no existing Jira client or test-plan creator under `Chapter7_AI_agent`.
- The requested constitution filename is `LLM.md`; `BLAST.md` calls the equivalent file `gemini.md`. This project uses `LLM.md` as the requested name.
- The user approved Groq and requested an open GPT 120B-class model; the app defaults to `openai/gpt-oss-120b` and keeps the model configurable.
- The phrase "J. key of growth" was interpreted as the Groq API key because it appeared in the settings/integration context. This is an explicit low-confidence interpretation that can be renamed if the user meant a separate credential.
- The app now lives in `Chapter7_AI_agent` and provides prompt extraction, Jira retrieval, Groq generation, JSON validation, Markdown rendering, and settings.

## Unknowns That Block Implementation

- Jira deployment type: Cloud, Server, or Data Center.
- Jira base URL and API version.
- Authentication method and scopes/permissions.
- Exact issue fields that form the source of truth.
- Whether comments, attachments, linked issues, and custom fields are in scope.
- Test plan structure, required test types, and delivery destination.
- LLM provider/model, data retention policy, and whether Jira content may leave the Jira environment.
- Expected behavior for an invalid ID, missing issue, permission denial, empty description, or incomplete acceptance criteria.

## Candidate Jira Retrieval Request

The following is a Jira Cloud-style REST request template. Confirm the deployment and API documentation before use. Do not place credentials directly in a command, commit them, or log them.

```bash
curl --request GET \
  --url "$JIRA_BASE_URL/rest/api/3/issue/$JIRA_ISSUE_KEY?fields=summary,description,issuetype,status,priority,labels,components,assignee,reporter,comment" \
  --user "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  --header "Accept: application/json"
```

Equivalent request shape:

```http
GET {JIRA_BASE_URL}/rest/api/3/issue/{JIRA_ISSUE_KEY}?fields=summary,description,issuetype,status,priority,labels,components,assignee,reporter,comment
Accept: application/json
Authorization: <deployment-approved-authentication>
```

For a Jira deployment that uses bearer authentication, the header may instead be:

```http
Authorization: Bearer ${JIRA_TOKEN}
```

That authentication choice must be confirmed before implementation. The `fields` list must also be adjusted after the source-of-truth decision, especially if acceptance criteria are stored in a custom field.

## Expected Retrieval Outcomes to Verify

- Success: response contains the requested issue key and approved fields.
- Invalid issue key: request is rejected by validation before the network call where possible.
- Missing issue or insufficient permission: preserve the HTTP status and a redacted error category; do not invent issue data.
- Authentication failure: stop the workflow and request credential/configuration correction.
- Rate limit or transient failure: apply the approved retry policy, then return a clear failure.
- Missing fields: mark them as missing in the normalized payload and prevent unsupported test-plan claims.

Exact status codes and Jira error bodies must be captured from the selected Jira environment rather than assumed.

## Proposed Evidence Mapping

The normalized source should retain where each value came from:

- `summary` -> Jira `fields.summary`
- `description` -> Jira `fields.description`
- `acceptanceCriteria` -> confirmed Jira field name, likely a configured/custom field
- `issueType` -> Jira `fields.issuetype`
- `status` -> Jira `fields.status`
- `priority` -> Jira `fields.priority`
- `comments` -> Jira `fields.comment.comments`, only if approved

The mapping is provisional until a real sanitized response is inspected.

## Implemented Retrieval and Generation

- Jira retrieval is implemented in `jira_client.py` and requests summary, description, issue metadata, labels, components, comments, and an optional configured acceptance field.
- Groq generation is implemented in `llm_client.py` using the OpenAI-compatible chat completions endpoint and structured JSON output.
- The UI is implemented in `app.py`; configuration and connection checks are in `pages/settings.py`.

## Research and Next Check

The next discriminating check is to enter a real Jira URL/email/token and Groq API key in Settings, test both connections, and generate one plan from an approved issue. The response should be reviewed for the configured acceptance-criteria field and the model name available to the Groq account.
