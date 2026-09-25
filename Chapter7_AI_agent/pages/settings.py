import streamlit as st

import config_store
import jira_client
import llm_client

st.set_page_config(page_title="SignalPlan Settings", page_icon="SP")

st.markdown("<div class='eyebrow'>SignalPlan / configuration</div>", unsafe_allow_html=True)
st.title("Connections")
st.caption("Credentials are stored in the local ignored config file. They are never included in generated prompts or logs.")

config = config_store.read_config()
with st.form("settings"):
    st.subheader("Jira")
    jira_url = st.text_input("Jira base URL", value=config.get("JIRA_URL", ""), placeholder="https://your-company.atlassian.net")
    jira_email = st.text_input("Jira email", value=config.get("JIRA_EMAIL", ""), placeholder="you@company.com")
    jira_token = st.text_input("Jira API token", value=config.get("JIRA_API_TOKEN", ""), type="password")
    acceptance_field = st.text_input("Acceptance criteria field (optional)", value=config.get("JIRA_ACCEPTANCE_FIELD", ""), placeholder="customfield_10020", help="Use the Jira field ID where your team stores acceptance criteria.")

    st.subheader("Groq")
    groq_key = st.text_input("Groq API key", value=config.get("GROQ_API_KEY", ""), type="password", help="This is the Groq API key used for the LLM connection.")
    groq_model = st.text_input("Groq model", value=config.get("GROQ_MODEL", "openai/gpt-oss-120b"))
    saved = st.form_submit_button("Save settings", type="primary")

if saved:
    config = config_store.write_config({
        "JIRA_URL": jira_url,
        "JIRA_EMAIL": jira_email,
        "JIRA_API_TOKEN": jira_token,
        "JIRA_ACCEPTANCE_FIELD": acceptance_field,
        "GROQ_API_KEY": groq_key,
        "GROQ_MODEL": groq_model,
    })
    st.success("Settings saved locally.")

st.divider()
st.subheader("Connection tests")
st.caption("Jira testing fetches the issue key below. Groq testing uses a small, non-sensitive request.")
test_issue = st.text_input("Jira issue key for connection test", value="PROJ-123")
col1, col2 = st.columns(2)
with col1:
    if st.button("Test Jira", use_container_width=True):
        current = config_store.read_config()
        try:
            issue = jira_client.check_connection(current["JIRA_URL"], current["JIRA_EMAIL"], current["JIRA_API_TOKEN"], test_issue)
            st.success(f"Jira connected. Found {issue['issueKey']}.")
        except jira_client.JiraError as exc:
            st.error(str(exc))
with col2:
    if st.button("Test Groq", use_container_width=True):
        current = config_store.read_config()
        try:
            reply = llm_client.check_connection(current["GROQ_API_KEY"], current.get("GROQ_MODEL", "openai/gpt-oss-120b"))
            st.success(f"Groq connected: {reply[:80]}")
        except llm_client.LLMError as exc:
            st.error(str(exc))

st.page_link("app.py", label="Back to studio")
