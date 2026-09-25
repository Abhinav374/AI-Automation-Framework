# Test Plan Creator - Task Plan

## Protocol Status

- Protocol: B.L.A.S.T. Protocol 0 through Phase 4.
- Objective: Create a test plan creator that accepts a Jira issue ID and produces a test plan from verified Jira data.
- Current status: Phases 1 through 4 implemented as a local Streamlit prototype.
- Scope: Jira retrieval, normalized evidence, Groq test-plan generation, validation, Markdown rendering, settings, and connection tests.

## North Star

Given a Jira issue ID, retrieve the issue data that the user authorizes, normalize it into a deterministic input payload, and generate a traceable test plan whose statements are grounded in the Jira source.

The approved delivery is a simple local UI. The user enters a natural-language request containing a Jira key; the app fetches the issue and renders a downloadable Markdown test plan.

## Discovery Checklist - Required Before Coding

- [x] North Star: User enters a prompt such as "Fetch this Jira and create a test plan."
- [x] Integrations: Jira REST API and Groq OpenAI-compatible API approved.
- [x] Credentials: Jira URL/email/token and Groq API key are configurable in Settings and ignored by Git.
- [x] Source of truth: Summary, description, issue metadata, comments, and an optional configured acceptance-criteria field.
- [x] Delivery payload: Rendered Markdown with downloadable file and visible normalized JSON.
- [x] Behavioral rules: Grounded output, evidence paths, explicit gaps, and deterministic validation.
- [x] Privacy and access: No attachments or linked issues are sent; credentials are excluded from prompts and logs.

## Blueprint Checklist

- [x] Define the Jira issue input contract and validate issue-key format.
- [x] Define the normalized Jira source schema.
- [x] Define the test-plan output schema.
- [x] Define traceability from every test case to source fields or quoted evidence.
- [x] Define behavior for missing, inaccessible, or incomplete Jira data.
- [x] Define deterministic validation rules separate from LLM generation.
- [x] Define authentication, timeout, rate-limit, and redaction policies.
- [x] Define Jira and Groq connectivity checks in Settings.
- [x] Define the architecture SOP before implementation.
- [x] Implement atomic integration modules in the Chapter 7 app.
- [x] Add compile-level validation for the Python modules.
- [ ] Add live integration tests using an approved Jira issue and Groq key.
- [x] Document setup, environment variables, commands, and known limitations.
- [ ] Obtain user review of a sample generated test plan.

## Proposed Phases

### Phase 0 - Initialization

- [x] Read `BLAST.md`.
- [x] Create `task_plan.md`.
- [x] Create `findings.md`.
- [x] Create `progress.md`.
- [x] Create `LLM.md` as the requested project constitution.
- [x] Receive answers to discovery questions for the local prototype.
- [x] Receive approval for the blueprint and schemas through the implementation request.

### Phase 1 - Blueprint

- [x] Confirm requirements and source fields.
- [x] Finalize JSON input/output schemas in `LLM.md`.
- [x] Write the architecture SOP.
- [x] Define acceptance tests and failure cases.

### Phase 2 - Link

- [x] Configure Jira connection using Settings, `.env`, or local ignored config.
- [ ] Verify authentication and issue retrieval against an approved live test issue.
- [x] Record response shape, permissions, rate limits, and error behavior in the client.
- [x] Stop generation when the Jira link cannot be verified.

### Phase 3 - Architect

- [x] Implement Jira retrieval and normalization as deterministic modules.
- [x] Implement schema validation and evidence tracking.
- [x] Implement test-plan generation through Groq.
- [x] Implement output validation and refusal of unsupported claims.
- [ ] Add focused live tests and sanitized fixtures.

### Phase 4 - Stylize and Trigger

- [x] Format the approved output as Markdown for download.
- [x] Add the Streamlit prompt-driven user-facing entry point.
- [x] Add settings, connection tests, redaction, and failure messages.
- [ ] Obtain feedback from a live Jira/Groq run and document final operating instructions.

## Protocol 0 Exit Criteria

- [x] All five discovery questions are answered for the prototype.
- [x] Jira Cloud-style API contract is implemented; deployment-specific field IDs remain configurable.
- [x] Input, normalized-source, and output schemas are implemented.
- [x] Behavioral rules and anti-hallucination policy are implemented.
- [x] Delivery mechanism is approved and implemented.
- [x] This blueprint is approved through the implementation request.

Live Jira and Groq requests require credentials entered by the user. The prototype does not write to Jira.
