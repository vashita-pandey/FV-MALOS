import config
import os
import json
import time
from cerebras.cloud.sdk import Cerebras
from verification_engine import (
    FormalVerifier, AgentSpec, ActionType,
    VerificationResult, get_default_agents
)

cerebras_client = Cerebras(api_key=os.environ.get("CEREBRAS_API_KEY", ""))
def call_llm(prompt: str) -> str:
    response = cerebras_client.chat.completions.create(
        model="gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

# ── Setup ──────────────────────────────────────────────────────
verifier = FormalVerifier()
agents   = get_default_agents()

# ── Task result ────────────────────────────────────────────────
class TaskResult:
    def __init__(self, agent_name, task, action_type, params,
                 verification, output=None):
        self.agent_name   = agent_name
        self.task         = task
        self.action_type  = action_type
        self.params       = params
        self.verification = verification
        self.output       = output
        self.timestamp    = time.time()

# ── Agent executor ─────────────────────────────────────────────
def agent_think(agent: AgentSpec, task: str, context: str = "") -> dict:
    prompt = f"""You are {agent.name}, an AI agent with role: {agent.role}

Your allowed actions: {[a.value for a in agent.allowed_actions]}

Task: {task}
Context: {context}

Decide what single action to take. Return ONLY this JSON:
{{
  "action_type": "one of: {[a.value for a in agent.allowed_actions]}",
  "params": {{}},
  "reasoning": "why this action"
}}

For web_search: params = {{"query": "search terms"}}
For code_execute: params = {{"code": "python code", "language": "python"}}
For file_read: params = {{"path": "filename.txt"}}
For file_write: params = {{"path": "filename.txt", "content": "text"}}
For send_message: params = {{"message": "text", "to": "agent_name"}}
For api_call: params = {{"endpoint": "url", "method": "GET"}}"""

    raw = call_llm(prompt)
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    try:
        return json.loads(raw)
    except:
        return {
            "action_type": "send_message",
            "params": {"message": raw[:200], "to": "OrchestratorAgent"},
            "reasoning": "Fallback to message"
        }

def simulate_action(action_type: str, params: dict) -> str:
    if action_type == "web_search":
        return f"[Simulated] Search results for '{params.get('query')}': Found 10 relevant articles."
    elif action_type == "code_execute":
        return f"[Simulated] Code executed. Output: 'Hello from {params.get('language','python')}'"
    elif action_type == "file_read":
        return f"[Simulated] File '{params.get('path')}' read. Content: 'Sample content...'"
    elif action_type == "file_write":
        return f"[Simulated] Written {len(params.get('content',''))} chars to '{params.get('path')}'"
    elif action_type == "send_message":
        return f"[Simulated] Message sent to {params.get('to')}: '{params.get('message','')[:50]}'"
    elif action_type == "api_call":
        return f"[Simulated] API call to {params.get('endpoint')} returned 200 OK"
    return "[Simulated] Action completed"

# ── Multi-agent pipeline ───────────────────────────────────────
def run_multi_agent_pipeline(user_task: str):
    results = []
    print(f"\n{'═'*60}")
    print(f"TASK: {user_task}")
    print(f"{'═'*60}")

    # Step 1: Orchestrator plans
    plan_prompt = f"""Break this task into 3-4 subtasks for specialist agents.
Available agents: ResearchAgent, CodeAgent, FileAgent
Task: {user_task}

Return JSON:
{{
  "plan": [
    {{"agent": "AgentName", "subtask": "description", "priority": 1}},
    {{"agent": "AgentName", "subtask": "description", "priority": 2}},
    {{"agent": "AgentName", "subtask": "description", "priority": 3}}
  ],
  "summary": "overall approach"
}}
Return ONLY the JSON."""

    print(f"\n[OrchestratorAgent] Planning pipeline...")
    raw_plan = call_llm(plan_prompt)
    if "```" in raw_plan:
        raw_plan = raw_plan.split("```")[1]
        if raw_plan.startswith("json"): raw_plan = raw_plan[4:]

    try:
        plan     = json.loads(raw_plan)
        print(f"[OrchestratorAgent] Plan: {plan.get('summary','')}")
        subtasks = plan.get("plan", [])
    except:
        subtasks = [{"agent": "ResearchAgent", "subtask": user_task, "priority": 1}]

    # Step 2: Execute each subtask with formal verification
    context = ""
    for i, subtask in enumerate(subtasks):
        agent_name = subtask.get("agent", "ResearchAgent")
        if agent_name not in agents:
            agent_name = "ResearchAgent"

        agent = agents[agent_name]
        task  = subtask.get("subtask", user_task)

        print(f"\n[Step {i+1}] {agent_name}: {task[:60]}...")

        decision        = agent_think(agent, task, context)
        action_type_str = decision.get("action_type", "send_message")
        params          = decision.get("params", {})
        reasoning       = decision.get("reasoning", "")

        print(f"  → Wants to   : {action_type_str}")
        print(f"  → Reasoning  : {reasoning[:80]}")
        print(f"  → Verifying formally...")

        try:
            action_type = ActionType(action_type_str)
        except:
            action_type = ActionType.SEND_MESSAGE

        verification = verifier.verify(agent, action_type, params)

        if verification.verified:
            print(f"  ✅ VERIFIED — executing action")
            output   = simulate_action(action_type_str, params)
            context += f"\n{agent_name} completed: {output}"
            print(f"  → Output: {output[:80]}")
        else:
            print(f"  ❌ BLOCKED — {verification.reason}")
            safe_params  = {"message": f"Task blocked: {task[:100]}", "to": "OrchestratorAgent"}
            verification = verifier.verify(agent, ActionType.SEND_MESSAGE, safe_params)
            output       = simulate_action("send_message", safe_params)
            print(f"  → Fallback: {output[:60]}")

        results.append(TaskResult(
            agent_name=agent_name, task=task,
            action_type=action_type_str, params=params,
            verification=verification, output=output
        ))
        time.sleep(0.3)

    # Step 3: Final synthesis
    print(f"\n[OrchestratorAgent] Synthesizing final answer...")
    synthesis = call_llm(f"""Based on these agent outputs, answer: {user_task}

Agent outputs: {context}

Give a clear concise answer in 3-5 sentences.""")

    print(f"\n{'═'*60}")
    print(f"FINAL ANSWER:")
    print(f"{'═'*60}")
    print(synthesis[:600])

    # Save
    os.makedirs("data", exist_ok=True)
    with open("data/last_run.json", "w") as f:
        json.dump({
            "task":         user_task,
            "steps":        len(results),
            "verified":     sum(1 for r in results if r.verification.verified),
            "blocked":      sum(1 for r in results if not r.verification.verified),
            "final_answer": synthesis,
            "steps_detail": [{
                "agent":    r.agent_name,
                "task":     r.task[:100],
                "action":   r.action_type,
                "verified": r.verification.verified,
                "output":   r.output[:100] if r.output else ""
            } for r in results]
        }, f, indent=2)

    return results, synthesis

# ── Test ───────────────────────────────────────────────────────
if __name__ == "__main__":
    results, answer = run_multi_agent_pipeline(
        "Research the latest advances in renewable energy and write a summary report"
    )
    verified = sum(1 for r in results if r.verification.verified)
    print(f"\n✓ Pipeline complete: {len(results)} steps, {verified} verified")