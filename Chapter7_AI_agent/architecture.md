# SignalPlan Architecture SOP

## Goal

Accept a plain-language request containing a Jira issue key and return a Markdown test plan grounded in verified Jira fields.

## Flow

1. Extract and validate an issue key locally.
2. Retrieve approved fields from Jira REST API v3 using configured credentials.
3. Flatten Jira ADF text and normalize the source payload.
4. Preserve evidence paths and list missing fields.
5. Send the redacted normalized payload to Groq using the configured model.
6. Validate the returned JSON shape deterministically.
7. Render the plan and expose the source JSON for review.

## Failure behavior

- Missing settings: stop before any network request.
- Invalid issue key: stop before any network request.
- Jira 401, 403, 404, timeout, or malformed JSON: show a categorized error and do not call Groq.
- Groq 401, 403, 429, timeout, or malformed output: show a categorized error and do not render a plan.
- Missing Jira evidence: retain the gap in the source and require the model to mark it as a gap.

## Configuration

Secrets may come from `.env` or the local ignored `config.json`. They must not enter prompts, logs, committed files, or rendered plans.

## Acceptance checks

- A valid prompt containing `PROJ-123` reaches the Jira retrieval boundary.
- An invalid prompt is rejected locally.
- Settings can be saved and reloaded.
- Jira and Groq connection buttons make their respective requests.
- A valid Groq JSON response validates and renders as Markdown.
- Invalid Groq JSON is rejected.
