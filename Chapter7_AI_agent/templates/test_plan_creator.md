# Grounding Contract

The application sends a normalized Jira source to Groq as structured JSON. The model must:

- Use only supplied Jira evidence.
- Mark missing requirements as gaps.
- Preserve source paths for each test case.
- Return JSON matching the schema in `LLM.md`.
- Avoid secrets and unnecessary personal data.
