# SignalPlan

SignalPlan is a small Streamlit app that retrieves a Jira issue and generates a grounded test plan with Groq.

## Run locally

```powershell
cd c:\AI-Automation-Framework\Chapter7_AI_agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit, then use **Settings** to add:

- Jira base URL, email, API token
- Optional Jira acceptance-criteria field ID
- Groq API key
- Groq model, defaulting to `openai/gpt-oss-120b`

The app stores settings in `config.json`, which is ignored by Git. No credentials are sent to the LLM. The first generation request retrieves only approved Jira fields, normalizes them, asks Groq for structured JSON, validates that JSON, and renders Markdown with evidence paths.

## Configuration through `.env`

```text
JIRA_URL=https://your-company.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=replace-me
JIRA_ACCEPTANCE_FIELD=customfield_10020
GROQ_API_KEY=replace-me
GROQ_MODEL=openai/gpt-oss-120b
```

## Safety boundary

This prototype reads Jira and generates a plan. It does not write comments or modify Jira issues. Missing evidence is surfaced as a gap rather than invented. Confirm the model name is available for your Groq account before using it in production.
