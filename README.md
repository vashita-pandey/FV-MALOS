# 🔐 FV-MALOS — Formally Verified Multi-Agent LLM Operating System

A multi-agent AI system where every agent action is mathematically verified before execution using Hoare Logic inspired precondition checking.

## What it does
- **4 specialized agents** — OrchestratorAgent, ResearchAgent, CodeAgent, FileAgent
- **3-layer formal verification** — action type check → forbidden pattern check → formal constraint evaluation
- **Hoare Logic inspired** — {P} C {Q}: preconditions proven before any action executes
- **Live proof traces** — every verification decision shown step by step
- **Interactive dashboard** — run pipelines, test verifications, inspect agent constraints

## Why it matters
Most AI agent systems rely on prompt instructions for safety. Prompts can be bypassed. FV-MALOS uses mathematical precondition checking — safety is proven, not hoped for.

## Example
FileAgent trying to send_message → **BLOCKED** (not in allowed actions)  
CodeAgent running `subprocess` → **BLOCKED** (forbidden pattern)  
ResearchAgent searching AI papers → **VERIFIED** (all constraints satisfied)

## Tech stack
`Python` `Cerebras API` `Streamlit` `Pydantic` `NetworkX` `Formal Verification`

## Run locally
```bash
pip install -r requirements.txt
# Add CEREBRAS_API_KEY to config.py
python -m streamlit run app.py
```