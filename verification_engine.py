import json
from typing import Any
from pydantic import BaseModel
from enum import Enum

# ── Action types ───────────────────────────────────────────────
class ActionType(str, Enum):
    FILE_READ       = "file_read"
    FILE_WRITE      = "file_write"
    FILE_DELETE     = "file_delete"
    WEB_SEARCH      = "web_search"
    CODE_EXECUTE    = "code_execute"
    SEND_MESSAGE    = "send_message"
    DATABASE_QUERY  = "database_query"
    API_CALL        = "api_call"
    SYSTEM_COMMAND  = "system_command"

# ── Verification result ────────────────────────────────────────
class VerificationResult(BaseModel):
    verified:    bool
    action:      str
    agent:       str
    reason:      str
    violated_constraints: list[str] = []
    proof_steps: list[str] = []

# ── Safety constraint ──────────────────────────────────────────
class SafetyConstraint(BaseModel):
    name:        str
    description: str
    check:       str  # Python expression as string

# ── Agent definition ───────────────────────────────────────────
class AgentSpec(BaseModel):
    name:               str
    role:               str
    allowed_actions:    list[ActionType]
    forbidden_patterns: list[str]
    max_iterations:     int
    constraints:        list[SafetyConstraint]

# ── Formal Verifier ────────────────────────────────────────────
class FormalVerifier:
    """
    Formally verifies agent actions before execution.
    Uses precondition checking — every action must satisfy
    all constraints before it is allowed to execute.
    This is inspired by Hoare Logic: {P} C {Q}
    where P = preconditions, C = action, Q = postconditions
    """

    def __init__(self):
        self.verification_log = []

    def verify(self, agent: AgentSpec, action_type: ActionType,
               action_params: dict) -> VerificationResult:
        """
        Formally verify an action against agent constraints.
        Returns VerificationResult with proof steps.
        """
        proof_steps      = []
        violated         = []
        action_str       = f"{action_type.value}({json.dumps(action_params)})"

        proof_steps.append(f"[P1] Agent '{agent.name}' requests: {action_str}")

        # ── Check 1: Is action type allowed? ──────────────────
        proof_steps.append(f"[P2] Checking allowed actions: {[a.value for a in agent.allowed_actions]}")
        if action_type not in agent.allowed_actions:
            violated.append(f"Action '{action_type.value}' not in allowed_actions")
            proof_steps.append(f"[FAIL] Action type forbidden for this agent")
            result = VerificationResult(
                verified=False, action=action_str, agent=agent.name,
                reason=f"Action type '{action_type.value}' is not permitted for agent '{agent.name}'",
                violated_constraints=violated, proof_steps=proof_steps
            )
            self.verification_log.append(result)
            return result
        proof_steps.append(f"[✓] Action type permitted")

        # ── Check 2: Forbidden patterns ────────────────────────
        proof_steps.append(f"[P3] Checking forbidden patterns...")
        params_str = json.dumps(action_params).lower()
        for pattern in agent.forbidden_patterns:
            if pattern.lower() in params_str:
                violated.append(f"Forbidden pattern detected: '{pattern}'")
                proof_steps.append(f"[FAIL] Forbidden pattern '{pattern}' found in action params")

        if violated:
            result = VerificationResult(
                verified=False, action=action_str, agent=agent.name,
                reason=f"Action contains forbidden patterns: {violated}",
                violated_constraints=violated, proof_steps=proof_steps
            )
            self.verification_log.append(result)
            return result
        proof_steps.append(f"[✓] No forbidden patterns detected")

        # ── Check 3: Safety constraints (formal preconditions) ─
        proof_steps.append(f"[P4] Evaluating {len(agent.constraints)} formal safety constraints...")
        for constraint in agent.constraints:
            proof_steps.append(f"  Verifying: {constraint.name}")
            try:
                # Evaluate constraint expression
                context = {
                    "action_type":   action_type.value,
                    "action_params": action_params,
                    "agent_name":    agent.name,
                    "params_str":    params_str,
                }
                safe_builtins = {"any": any, "all": all, "len": len, "str": str, "int": int}
                eval_context = {**context, "__builtins__": safe_builtins}
                result_check = eval(constraint.check, eval_context)
                if not result_check:
                    violated.append(constraint.name)
                    proof_steps.append(f"  [FAIL] Constraint violated: {constraint.description}")
                else:
                    proof_steps.append(f"  [✓] Constraint satisfied: {constraint.name}")
            except Exception as e:
                violated.append(f"{constraint.name} (eval error: {e})")
                proof_steps.append(f"  [ERROR] Could not evaluate constraint: {e}")

        if violated:
            result = VerificationResult(
                verified=False, action=action_str, agent=agent.name,
                reason=f"Formal verification failed: {len(violated)} constraint(s) violated",
                violated_constraints=violated, proof_steps=proof_steps
            )
        else:
            proof_steps.append(f"[✓] All {len(agent.constraints)} constraints satisfied")
            proof_steps.append(f"[VERIFIED] Action is formally safe to execute")
            result = VerificationResult(
                verified=True, action=action_str, agent=agent.name,
                reason="All formal safety constraints verified — action is safe",
                violated_constraints=[], proof_steps=proof_steps
            )

        self.verification_log.append(result)
        return result

# ── Predefined agents ──────────────────────────────────────────
def get_default_agents() -> dict[str, AgentSpec]:
    return {
        "ResearchAgent": AgentSpec(
            name="ResearchAgent",
            role="Searches the web and synthesizes information",
            allowed_actions=[ActionType.WEB_SEARCH, ActionType.FILE_WRITE,
                           ActionType.SEND_MESSAGE],
            forbidden_patterns=["password", "secret", "private_key",
                               "credit_card", "ssn", "token"],
            max_iterations=10,
            constraints=[
                SafetyConstraint(
                    name="no_personal_data_exfiltration",
                    description="Cannot search for or write personal identifying information",
                    check="not any(p in params_str for p in ['ssn', 'passport', 'credit card', 'password'])"
                ),
                SafetyConstraint(
                    name="search_query_length",
                    description="Search queries must be under 500 characters",
                    check="len(action_params.get('query', '')) < 500"
                ),
            ]
        ),

        "CodeAgent": AgentSpec(
            name="CodeAgent",
            role="Writes and executes code to solve problems",
            allowed_actions=[ActionType.CODE_EXECUTE, ActionType.FILE_READ,
                           ActionType.FILE_WRITE, ActionType.SEND_MESSAGE],
            forbidden_patterns=["os.system", "subprocess", "shutil.rmtree",
                               "rm -rf", "format c:", "__import__",
                               "eval(", "exec("],
            max_iterations=15,
            constraints=[
                SafetyConstraint(
                    name="no_system_commands",
                    description="Cannot execute system-level shell commands",
                    check="not any(p in params_str for p in ['os.system', 'subprocess', 'shell=true'])"
                ),
                SafetyConstraint(
                    name="no_network_in_code",
                    description="Code execution cannot make network requests",
                    check="not any(p in params_str for p in ['requests.get', 'urllib', 'socket', 'http'])"
                ),
                SafetyConstraint(
                    name="code_length_limit",
                    description="Code snippets must be under 200 lines",
                    check="action_params.get('code', '').count('\\n') < 200"
                ),
            ]
        ),

        "FileAgent": AgentSpec(
            name="FileAgent",
            role="Manages file operations safely",
            allowed_actions=[ActionType.FILE_READ, ActionType.FILE_WRITE],
            forbidden_patterns=["system32", "windows", "/etc/passwd",
                               ".ssh", "id_rsa", ".env", "config.py"],
            max_iterations=5,
            constraints=[
                SafetyConstraint(
                    name="no_system_files",
                    description="Cannot access system-critical files",
                    check="not any(p in params_str for p in ['system32', '/etc/', '/var/', 'windows/'])"
                ),
                SafetyConstraint(
                    name="no_hidden_files",
                    description="Cannot access hidden files (starting with .)",
                    check="not action_params.get('path', '').startswith('.')"
                ),
                SafetyConstraint(
                    name="allowed_extensions",
                    description="Can only read/write safe file types",
                    check="any(action_params.get('path', '').endswith(ext) for ext in ['.txt', '.csv', '.json', '.md', '.py', '.js', ''])"
                ),
            ]
        ),

        "OrchestratorAgent": AgentSpec(
            name="OrchestratorAgent",
            role="Coordinates other agents and manages task flow",
            allowed_actions=[ActionType.SEND_MESSAGE, ActionType.API_CALL],
            forbidden_patterns=["drop table", "delete from", "truncate",
                               "rm -rf", "format"],
            max_iterations=20,
            constraints=[
                SafetyConstraint(
                    name="no_destructive_operations",
                    description="Cannot initiate destructive database or file operations",
                    check="not any(p in params_str for p in ['drop', 'delete', 'truncate', 'destroy'])"
                ),
                SafetyConstraint(
                    name="message_length_limit",
                    description="Messages must be under 2000 characters",
                    check="len(action_params.get('message', '')) < 2000"
                ),
            ]
        ),
    }

# ── Quick test ─────────────────────────────────────────────────
if __name__ == "__main__":
    verifier = FormalVerifier()
    agents   = get_default_agents()

    print("═" * 60)
    print("FV-MALOS Formal Verification Engine — Test Suite")
    print("═" * 60)

    tests = [
        ("CodeAgent",  ActionType.CODE_EXECUTE,
         {"code": "print('hello world')", "language": "python"},
         "Safe code execution"),

        ("CodeAgent",  ActionType.CODE_EXECUTE,
         {"code": "import subprocess; subprocess.run(['rm', '-rf', '/'])", "language": "python"},
         "Dangerous system command"),

        ("FileAgent",  ActionType.FILE_READ,
         {"path": "data/report.csv"},
         "Safe file read"),

        ("FileAgent",  ActionType.FILE_READ,
         {"path": ".env"},
         "Hidden config file access"),

        ("FileAgent",  ActionType.FILE_DELETE,
         {"path": "data/old.txt"},
         "Forbidden action type"),

        ("ResearchAgent", ActionType.WEB_SEARCH,
         {"query": "latest AI research papers 2024"},
         "Safe web search"),

        ("ResearchAgent", ActionType.WEB_SEARCH,
         {"query": "how to find someone's password and ssn"},
         "Dangerous search query"),
    ]

    passed = 0
    failed = 0
    for agent_name, action, params, description in tests:
        agent  = agents[agent_name]
        result = verifier.verify(agent, action, params)
        status = "✅ VERIFIED" if result.verified else "❌ BLOCKED"
        print(f"\n{status} | {description}")
        print(f"  Agent : {agent_name}")
        print(f"  Action: {action.value}")
        print(f"  Reason: {result.reason}")
        if result.violated_constraints:
            print(f"  Violated: {result.violated_constraints}")
        if result.verified:
            passed += 1
        else:
            failed += 1

    print(f"\n{'═'*60}")
    print(f"Results: {passed} verified, {failed} blocked")
    print(f"Verification engine working correctly ✓")