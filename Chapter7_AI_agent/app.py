import json
import re
from pathlib import Path

import streamlit as st

import config_store
import jira_client
import llm_client

st.set_page_config(page_title="SignalPlan", page_icon="SP", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@400;500;600;700&display=swap');
    :root { --ink: #17231d; --muted: #6c786f; --paper: #f5f3ed; --lime: #c7f36b; --coral: #ff826e; --line: #d9ded2; }
    .stApp { background: var(--paper); color: var(--ink); }
    h1, h2, h3, p, label, .stMarkdown { font-family: 'Space Grotesk', sans-serif; }
    h1 { letter-spacing: 0; font-size: 3.2rem; line-height: 1; }
    .eyebrow { color: var(--coral); font: 500 0.75rem 'DM Mono', monospace; letter-spacing: .08em; text-transform: uppercase; }
    .hero { padding: 2rem 0 1rem; border-bottom: 1px solid var(--line); }
    .hero-copy { max-width: 700px; color: var(--muted); font-size: 1.05rem; }
    .signal { background: var(--lime); padding: .18rem .5rem; color: var(--ink); }
    .source-box, .plan-box { border: 1px solid var(--line); background: #fbfaf6; padding: 1.25rem; min-height: 150px; }
    .source-label { color: var(--muted); font: 500 .7rem 'DM Mono', monospace; text-transform: uppercase; letter-spacing: .08em; }
    div[data-testid='stSidebar'] { background: #e8eee2; border-right: 1px solid var(--line); }
    .stButton > button, .stDownloadButton > button { border-radius: 2px; border: 1px solid var(--ink); font-family: 'DM Mono', monospace; }
    .stButton > button[kind='primary'] { background: var(--ink); color: var(--lime); }
    </style>
    """,
    unsafe_allow_html=True,
)

BASE_DIR = Path(__file__).resolve().parent


def is_configured(config: dict) -> bool:
    return all(config.get(key) for key in ("JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "GROQ_API_KEY"))


def plan_markdown(plan: dict) -> str:
    lines = [f"# {plan['title']}", "", f"**Jira issue:** `{plan['issueKey']}`", "", "## Scope", ""]
    for label, key in (("In scope", "inScope"), ("Out of scope", "outOfScope"), ("Assumptions", "assumptions")):
        lines.extend([f"### {label}", ""])
        values = plan.get("scope", {}).get(key, []) or ["Not specified"]
        lines.extend(f"- {value}" for value in values)
        lines.append("")
    lines.extend(["## Test cases", ""])
    for case in plan.get("testCases", []):
        lines.extend([f"### {case.get('id', 'TC')} - {case.get('title', 'Untitled')}", "", f"- **Type:** {case.get('type', 'not specified')}", f"- **Priority:** {case.get('priority', 'not specified')}", f"- **Coverage:** {case.get('coverage', 'not specified')}", f"- **Evidence:** {', '.join(case.get('sourceEvidence', [])) or 'Not specified'}", ""])
        if case.get("preconditions"):
            lines.append("**Preconditions**")
            lines.extend(f"- {item}" for item in case["preconditions"])
            lines.append("")
        lines.append("| Step | Action | Expected result |")
        lines.append("| --- | --- | --- |")
        for index, step in enumerate(case.get("steps", []), 1):
            lines.append(f"| {index} | {step.get('action', '')} | {step.get('expectedResult', '')} |")
        lines.append("")
    lines.extend(["## Gaps", ""])
    lines.extend(f"- {gap}" for gap in (plan.get("gaps") or ["None recorded"]))
    return "\n".join(lines)


config = config_store.read_config()
with st.sidebar:
    st.markdown('<div class="eyebrow">SignalPlan / 01</div>', unsafe_allow_html=True)
    st.title("Test plan studio")
    st.caption("Jira evidence in. Grounded QA plan out.")
    st.divider()
    if is_configured(config):
        st.success("Connections configured")
    else:
        st.warning("Add Jira and Groq settings")
    st.page_link("pages/settings.py", label="Open settings", icon="⚙")
    st.markdown("---")
    st.caption("Protocol 0 → 4\n\nRetrieve → normalize → generate → validate")

st.markdown('<div class="hero"><div class="eyebrow">B.L.A.S.T. / live workspace</div><h1>Turn a Jira issue into a <span class="signal">test plan.</span></h1><p class="hero-copy">Give the studio a plain-language request. It finds the issue, preserves the evidence trail, and asks Groq to shape it into a practical QA plan.</p></div>', unsafe_allow_html=True)
st.write("")

if "last_issue" not in st.session_state:
    st.session_state.last_issue = None
if "last_plan" not in st.session_state:
    st.session_state.last_plan = None
if "last_source" not in st.session_state:
    st.session_state.last_source = None

prompt = st.text_area("Request", placeholder="Fetch PROJ-123 and create a test plan", height=100, label_visibility="collapsed")
col_a, col_b = st.columns([1, 3])
with col_a:
    generate = st.button("Generate plan", type="primary", use_container_width=True)
with col_b:
    st.caption("Example: `Fetch PAY-482 and create a test plan for the acceptance criteria.`")

if generate:
    issue_key = jira_client.extract_issue_key(prompt)
    if not issue_key:
        st.error("Add a Jira issue key such as PROJ-123 to your request.")
    elif not is_configured(config):
        st.error("Complete the Jira and Groq settings before generating a plan.")
        st.page_link("pages/settings.py", label="Open settings")
    else:
        with st.status(f"Building a plan from {issue_key}", expanded=True) as status:
            try:
                st.write("Fetching approved Jira fields…")
                source = jira_client.fetch_issue(config["JIRA_URL"], config["JIRA_EMAIL"], config["JIRA_API_TOKEN"], issue_key, config.get("JIRA_ACCEPTANCE_FIELD", ""))
                st.write("Normalizing evidence and checking gaps…")
                plan = llm_client.generate_test_plan(source, config["GROQ_API_KEY"], config.get("GROQ_MODEL", "openai/gpt-oss-120b"))
                st.session_state.last_issue = issue_key
                st.session_state.last_source = source
                st.session_state.last_plan = plan
                status.update(label="Plan ready", state="complete")
            except (jira_client.JiraError, llm_client.LLMError) as exc:
                status.update(label="Plan stopped", state="error")
                st.error(str(exc))

if st.session_state.last_plan:
    plan = st.session_state.last_plan
    source = st.session_state.last_source
    st.divider()
    left, right = st.columns([1, 1.2])
    with left:
        st.markdown('<div class="source-label">Verified Jira source</div>', unsafe_allow_html=True)
        st.markdown(f"### {source['issueKey']}")
        fields = source["source"]["fields"]
        st.markdown(f"**{fields['summary'] or 'Summary not specified'}**")
        st.caption(f"{fields['issueType'] or 'Issue type not specified'} · {fields['status'] or 'Status not specified'} · {fields['priority'] or 'Priority not specified'}")
        st.markdown('<div class="source-box">' + (fields["description"] or "Description not specified.") + "</div>", unsafe_allow_html=True)
        if source.get("missingFields"):
            st.warning("Missing evidence: " + ", ".join(source["missingFields"]))
    with right:
        st.markdown('<div class="source-label">Generated QA plan</div>', unsafe_allow_html=True)
        st.markdown(f"### {plan.get('title', 'Test plan')}")
        st.caption(f"{len(plan.get('testCases', []))} test cases · {len(plan.get('gaps', []))} gaps · grounded: {plan.get('validation', {}).get('isGrounded', False)}")
        st.markdown(plan_markdown(plan))
        st.download_button("Download Markdown", plan_markdown(plan), file_name=f"{source['issueKey']}-test-plan.md", mime="text/markdown")
        with st.expander("View normalized source JSON"):
            st.json(source)
else:
    st.divider()
    st.info("Your generated plan will appear here with the Jira source and evidence trail side by side.")
