import config
import streamlit as st
import json
import os
import time
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from verification_engine import get_default_agents, FormalVerifier, ActionType
from agent_orchestrator import run_multi_agent_pipeline

st.set_page_config(page_title="FV-MALOS", page_icon="🔐", layout="wide")

st.markdown("""
<style>
  .main { background-color: #0f1117; }
  .metric-card { background:#1a1d27; border:1px solid #2a2d3a; border-radius:10px; padding:1rem 1.25rem; margin-bottom:0.5rem; }
  .metric-label { font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.05em; }
  .metric-value { font-size:26px; font-weight:600; color:#eee; }
  .verified { background:#1a2a1a; border-left:4px solid #1d9e75; border-radius:0 8px 8px 0; padding:0.75rem 1rem; margin:0.5rem 0; font-size:13px; color:#1d9e75; }
  .blocked  { background:#2a1a1a; border-left:4px solid #e05c2a; border-radius:0 8px 8px 0; padding:0.75rem 1rem; margin:0.5rem 0; font-size:13px; color:#e05c2a; }
  .proof-box { background:#1a1d27; border:1px solid #2a2d3a; border-radius:8px; padding:1rem; font-family:monospace; font-size:12px; color:#aaa; }
  h1,h2,h3 { color:#eee !important; }
</style>
""", unsafe_allow_html=True)

agents   = get_default_agents()
verifier = FormalVerifier()

# ── Header ─────────────────────────────────────────────────────
st.title("🔐 FV-MALOS")
st.markdown("*Formally Verified Multi-Agent LLM Operating System*")
st.divider()

tab1, tab2, tab3, tab4 = st.tabs([
    "🚀 Run Pipeline", "🔍 Verify Action", "🤖 Agents", "📖 How it works"
])

# ════════════════════════════════════════════════════
# Tab 1 — Run Pipeline
# ════════════════════════════════════════════════════
with tab1:
    st.subheader("Multi-agent task execution with formal verification")

    task = st.text_area(
        "Enter a task for the agent pipeline:",
        placeholder="e.g. Research quantum computing advances and write a technical summary",
        height=100
    )

    samples = [
        "Research climate change solutions and summarize key findings",
        "Analyze Python code best practices and create a style guide",
        "Find the latest AI research papers and extract key insights",
    ]
    st.markdown("**Quick samples:**")
    cols = st.columns(3)
    for i, sample in enumerate(samples):
        with cols[i]:
            if st.button(sample[:40]+"...", key=f"sample_{i}"):
                st.session_state["task_input"] = sample

    if "task_input" in st.session_state:
        task = st.session_state["task_input"]

    if st.button("▶ Run Pipeline", type="primary") and task.strip():
        with st.spinner("Running multi-agent pipeline with formal verification..."):
            results, final_answer = run_multi_agent_pipeline(task)

        st.divider()

        # Metrics
        verified_count = sum(1 for r in results if r.verification.verified)
        blocked_count  = len(results) - verified_count

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Total steps</div><div class="metric-value">{len(results)}</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Verified</div><div class="metric-value" style="color:#1d9e75;">{verified_count}</div></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Blocked</div><div class="metric-value" style="color:#e05c2a;">{blocked_count}</div></div>', unsafe_allow_html=True)
        with col4:
            safety = int(verified_count/len(results)*100) if results else 0
            st.markdown(f'<div class="metric-card"><div class="metric-label">Safety rate</div><div class="metric-value">{safety}%</div></div>', unsafe_allow_html=True)

        # Steps
        st.subheader("Pipeline execution trace")
        for i, r in enumerate(results):
            status = "✅ VERIFIED" if r.verification.verified else "❌ BLOCKED"
            css    = "verified" if r.verification.verified else "blocked"
            st.markdown(f"""<div class="{css}">
                <strong>[Step {i+1}] {r.agent_name}</strong> — {r.action_type}<br/>
                <span style="color:#888;">Task: {r.task[:80]}</span><br/>
                <span>{status}: {r.verification.reason[:100]}</span>
            </div>""", unsafe_allow_html=True)

            with st.expander(f"Proof steps for step {i+1}"):
                st.markdown('<div class="proof-box">' +
                           "<br/>".join(r.verification.proof_steps) +
                           '</div>', unsafe_allow_html=True)

        st.divider()
        st.subheader("Final answer")
        st.markdown(final_answer)

    # Show last run if exists
    elif os.path.exists("data/last_run.json"):
        with open("data/last_run.json") as f:
            last = json.load(f)
        st.info(f"Last run: '{last['task'][:60]}...' — {last['verified']}/{last['steps']} verified")

# ════════════════════════════════════════════════════
# Tab 2 — Verify Action
# ════════════════════════════════════════════════════
with tab2:
    st.subheader("Test formal verification on any action")
    st.markdown("See the full proof trace for any agent-action combination.")

    col1, col2 = st.columns(2)
    with col1:
        agent_name  = st.selectbox("Agent", list(agents.keys()))
        action_name = st.selectbox("Action type", [a.value for a in ActionType])
    with col2:
        param_key   = st.text_input("Parameter key", value="query")
        param_value = st.text_input("Parameter value", value="latest AI research")

    if st.button("🔍 Verify", type="primary"):
        agent  = agents[agent_name]
        try:
            action = ActionType(action_name)
        except:
            action = ActionType.SEND_MESSAGE

        params = {param_key: param_value}
        result = verifier.verify(agent, action, params)

        st.divider()
        if result.verified:
            st.success(f"✅ VERIFIED — {result.reason}")
        else:
            st.error(f"❌ BLOCKED — {result.reason}")

        if result.violated_constraints:
            st.markdown("**Violated constraints:**")
            for v in result.violated_constraints:
                st.markdown(f"- `{v}`")

        st.markdown("**Formal proof trace:**")
        st.markdown('<div class="proof-box">' +
                   "<br/>".join(result.proof_steps) +
                   '</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════
# Tab 3 — Agents
# ════════════════════════════════════════════════════
with tab3:
    st.subheader("Agent registry")

    for name, agent in agents.items():
        with st.expander(f"🤖 {name} — {agent.role}"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Allowed actions:**")
                for a in agent.allowed_actions:
                    st.markdown(f"✅ `{a.value}`")
                st.markdown("**Forbidden patterns:**")
                for p in agent.forbidden_patterns[:5]:
                    st.markdown(f"🚫 `{p}`")
            with col2:
                st.markdown("**Formal safety constraints:**")
                for c in agent.constraints:
                    st.markdown(f"**{c.name}**")
                    st.markdown(f"_{c.description}_")
                    st.code(c.check, language="python")

            st.markdown(f"**Max iterations:** {agent.max_iterations}")

# ════════════════════════════════════════════════════
# Tab 4 — How it works
# ════════════════════════════════════════════════════
with tab4:
    st.subheader("How FV-MALOS works")
    st.markdown("""
    ### The problem with current AI agents
    Most multi-agent systems rely on prompt instructions to prevent unsafe behavior.
    Prompts can be bypassed, misinterpreted, or ignored under adversarial conditions.

    ### Formal verification approach
    FV-MALOS uses **Hoare Logic** inspired precondition checking:

    > **{P} C {Q}** — if precondition P holds, after executing command C, postcondition Q holds.

    Every agent action must satisfy formal preconditions **before** execution.
    This is mathematically proven, not just prompted.

    ### Three verification layers
    1. **Action type check** — is this action in the agent's allowed set?
    2. **Forbidden pattern check** — does the action contain dangerous strings?
    3. **Formal constraint evaluation** — do all safety predicates evaluate to True?

    ### Agent roles
    - **OrchestratorAgent** — breaks tasks into subtasks, coordinates agents
    - **ResearchAgent** — web search and information synthesis
    - **CodeAgent** — code writing and execution (heavily constrained)
    - **FileAgent** — file read/write (path and extension restricted)

    ### Why this matters
    As AI agents gain more autonomy, formal safety guarantees become critical.
    FV-MALOS demonstrates that safety constraints can be mathematically verified,
    not just hoped for — a key requirement for production AI systems.
    """)