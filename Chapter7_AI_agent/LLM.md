# Project Constitution - LLM Boundary and Architecture

## Purpose

This document is the requested project constitution for a Jira-ID-driven test plan creator. It is equivalent to the `gemini.md` constitution named by `BLAST.md`, but keeps the filename requested in `Prompt_Used.md`.

The system must transform verified Jira evidence into a test plan without presenting unsupported assumptions as facts.

## Current Constitution Status

- Status: Implemented prototype, pending live credential validation.
- Protocol: B.L.A.S.T. Protocol 0 through Phase 4.
- Coding state: Core modules, UI, settings, and SOP are implemented.
- Unknowns must remain explicit. A missing requirement is not permission to infer one.

## Proposed JSON Schemas

### Request Input

```json
{
  "jiraIssueKey": "PROJECT-123",
  "options": {
    "includeComments": false,
    "includeAttachments": false,
    "includeLinkedIssues": false,
    "testTypes": ["functional", "negative", "boundary"]
  }
}
```

Rules for this input:

- `jiraIssueKey` is required and must be validated before retrieval.
- Optional flags default only after the user approves those defaults.
- The final test types and options are pending discovery.
- Credentials, tokens, and secrets are never part of this JSON payload.

### Normalized Jira Source

```json
{
  "issueKey": "PROJECT-123",
  "source": {
    "jiraBaseUrl": "https://jira.example.invalid",
    "retrievedAt": "2026-09-04T00:00:00Z",
    "fields": {
      "summary": "",
      "description": null,
      "acceptanceCriteria": null,
      "issueType": null,
      "status": null,
      "priority": null,
      "labels": [],
      "components": [],
      "comments": []
    }
  },
  "evidence": [
    {
      "sourcePath": "fields.summary",
      "valuePresent": true,
      "redactedValue": ""
    }
  ],
  "missingFields": [],
  "warnings": []
}
```

This is a provisional shape. The actual Jira response must determine the description format and the field name for acceptance criteria. `retrievedAt` is metadata, not product evidence.

### Test Plan Output

```json
{
  "issueKey": "PROJECT-123",
  "title": "",
  "scope": {
    "inScope": [],
    "outOfScope": [],
    "assumptions": []
  },
  "testCases": [
    {
      "id": "TC-001",
      "title": "",
      "type": "functional",
      "priority": "",
      "preconditions": [],
      "steps": [
        {
          "action": "",
          "expectedResult": ""
        }
      ],
      "sourceEvidence": ["fields.description"],
      "coverage": "direct"
    }
  ],
  "gaps": [],
  "validation": {
    "isGrounded": true,
    "missingEvidence": [],
    "warnings": []
  }
}
```

The implementation renders Markdown from this structured form, while the structured form remains the validation boundary. Groq defaults to `openai/gpt-oss-120b`, configurable in Settings.

## Behavioral Rules

1. Use only Jira data that was successfully retrieved and user-approved supplemental requirements.
2. Preserve source paths for claims and test cases.
3. Label inferred content as an assumption or gap; never silently turn it into a requirement.
4. If evidence is insufficient, produce a gap or refusal for that part of the plan.
5. Never fabricate acceptance criteria, expected results, API behavior, error codes, UI behavior, or test data.
6. Keep retrieval, normalization, generation, and validation separate.
7. Validate the generated output deterministically after the LLM response.
8. Do not send comments, attachments, linked issues, or secrets to an LLM unless explicitly approved.
9. Redact tokens, passwords, personal data, and unnecessary Jira metadata from logs.
10. Treat Jira as the source of truth only for the fields approved during discovery.
11. Do not write to Jira or alter source issues unless a separate write scope is explicitly approved.
12. Fail clearly on authentication failure, permission failure, missing issue, malformed response, or validation failure.
13. Make retries bounded and observable; never retry indefinitely.
14. Keep generated output deterministic through fixed schemas, explicit prompts, controlled options, and validation.

## Architectural Invariants

- Layer 1, Architecture: Markdown SOPs define goals, inputs, tool logic, and edge cases.
- Layer 2, Navigation: decision logic routes verified data between SOPs and tools; it does not invent business logic.
- Layer 3, Tools: deterministic scripts retrieve, normalize, validate, and render data atomically.
- Environment variables hold Jira configuration and credentials.
- Intermediate files use `.tmp/` if file storage is approved.
- The LLM may propose test cases, but deterministic code owns schema validation, evidence checks, redaction, and failure handling.
- Changes to logic require updating the SOP and constitution before code changes.
- The initial Jira connection must be verified before full generation logic is built.
- The prototype interprets the requested growth-side key as the Groq API key; no separate credential is currently modeled.

## Proposed Request Flow

1. Validate the Jira issue key.
2. Load non-secret configuration from the environment.
3. Retrieve only approved fields from Jira.
4. Normalize the response and attach evidence paths.
5. Stop or report gaps if required evidence is missing.
6. Pass the normalized, redacted payload to the approved LLM boundary.
7. Validate the structured output against the approved schema.
8. Check every test case for source evidence and unsupported assumptions.
9. Render the approved delivery format.
10. Log outcome categories without secrets or unnecessary issue content.

## Decisions Pending Live Validation

- Jira deployment and API version.
- Authentication and permissions.
- Required source fields and acceptance-criteria location.
- Confirmation that `openai/gpt-oss-120b` is enabled for the Groq account, or selection of another configured Groq model.
- Test-plan schema details and required test categories.
- Delivery destination and write permissions.
- Jira acceptance-criteria field ID and any deployment-specific API differences.
