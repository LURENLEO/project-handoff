"""Shared realistic semantic fixture, no credentials or external dependencies."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from handoff_core.context import DOMAINS
from handoff_core.common import now


def fact(id, statement, **extra):
    return dict(id=id, statement=statement, source=dict(kind="user_message", ref="Visible fixture request: complete add(a, b) and verify"),
                observed_at=now(), confidence="high", **extra)


def context(fingerprint=None):
    c = {d: [] for d in DOMAINS}
    c.update(schema_version="1.0.0", observed_fingerprint=fingerprint,
             coverage={d: dict(status="not_applicable", reason="Fixture has no entries in this domain; explicitly checked") for d in DOMAINS})
    c["intent"] = fact("I-1", "Finish arithmetic addition while preserving existing behavior",
                        original_goal="Complete add(a, b)", current_goal="Complete add(a, b) and verify negative operands",
                        acceptance=["add(2, 3) == 5", "add(-2, 3) == 1", "Existing subtract function remains unchanged"],
                        scope=["calculator.py", "test_calculator.py"], non_goals=["No dependencies, remote actions or broad refactoring"], corrections=[])
    c["constraints"] = [fact("C-1", "Preserve subtract(a, b) and the user's notes.txt")]
    c["authorization"] = [fact("A-1", "May edit calculator.py and run local unittest; no network or commits", actions=["edit", "local_test"], scope=["calculator.py", "test_calculator.py"])]
    c["work_items"] = [fact("T-1", "Implement add", status="implemented_unverified", acceptance=c["intent"]["acceptance"], done=["Function signature and docstring exist"], remaining=["Replace placeholder body", "Run tests"], files=[{"path": "calculator.py", "symbol": "add"}], depends_on=[], evidence_ids=["V-1"])]
    c["in_progress"] = [fact("P-1", "calculator.py:add still returns None; replace only its body", path="calculator.py", symbol="add", workaround=None)]
    c["decisions"] = [fact("D-1", "Use Python arithmetic; no conversion or extra libraries", reason="Inputs are numbers", alternatives=["String conversion rejected: changes semantics"], reopen_when="User requests coercion")]
    c["validation"] = [fact("V-1", "Tests have not been run after placeholder work", result="not_run", freshness="unknown", started_at=None, ended_at=None, exit_code=None, log=None, code_fingerprint=None, environment="Python 3.11+", command=dict(argv=["python", "-m", "unittest", "-v"], cwd_ref="project", env_names=[], purpose="Validate arithmetic behavior", side_effects="May create __pycache__"))]
    c["next_actions"] = [fact("N-1", "Complete arithmetic implementation", task_id="T-1", action="Read current project instructions, replace calculator.py:add placeholder with numeric addition, then run local unittest", preconditions=["Verify package and compare current files", "Preserve user's notes.txt changes"], files=[{"path": "calculator.py", "symbol": "add"}], expected_result="All arithmetic tests pass and subtract/notes remain unchanged", validation="python -m unittest -v", on_failure="Record failing assertion and investigate add; preserve existing user changes")]
    for d in DOMAINS:
        if c[d]:
            c["coverage"][d] = dict(status="complete", reason="Checked against visible fixture request and project files")
    return c
