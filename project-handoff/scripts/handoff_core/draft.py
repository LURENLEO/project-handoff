"""Generate a context draft from local evidence; semantic domains stay explicit TODO placeholders."""
import platform
import sys
from pathlib import Path
from .collect import collect
from .common import HandoffError, VERSION, encoded, now, result, write_bytes
from .context import DOMAINS

HINTS = {
    "intent": "state original_goal, current_goal, acceptance and scope from the current conversation",
    "constraints": "list standing constraints (scope, compatibility, things that must not change)",
    "authorization": "state what the current user authorized: files, commands, network, commits",
    "architecture": "note the architecture facts a continuing agent must know",
    "work_items": "enumerate work items with status; keep stable IDs when a previous state.json exists",
    "in_progress": "point at the exact half-finished edit a continuing agent resumes",
    "decisions": "record decisions with reasons; keep stable IDs and superseded_by links",
    "validation": "record how the work was or must be validated: structured command, result, evidence",
    "external_state": "list remote systems whose state is unknown or pending (deploys, pushes, migrations)",
    "collaboration": "note other agents, services or people touching this workspace",
    "next_actions": "declare the concrete next step with preconditions, expected result and failure plan",
    "gaps": "record what is unknown, inaccessible or not yet verified, with impact and resolution",
}


def placeholder(domain, observed_at):
    return dict(id="draft-" + domain, statement="TODO: " + HINTS[domain],
                source=dict(kind="draft_template", ref="draft template; replace from the visible conversation"),
                observed_at=observed_at, confidence="unknown")


def draft(root, out=None, store=None):
    root = Path(root).resolve()
    if not root.is_dir():
        raise HandoffError("Project root must exist", 4)
    observed_at = now()
    capture, _ = collect(root, store)
    git = capture["git"]
    c = {d: [] for d in DOMAINS}
    c["intent"] = placeholder("intent", observed_at)
    c["intent"].update(
        statement="TODO: state original_goal, current_goal, acceptance and scope from the current conversation",
        original_goal="TODO: original goal from the visible conversation",
        current_goal="TODO: current goal from the visible conversation",
        acceptance=[], scope=[], non_goals=[], corrections=[])
    summary = "Project root: " + root.name
    if git:
        summary += "; branch: " + (git["branch"] or "detached") + "; HEAD: " + (git["head"] or "unborn")[:12]
    c["project"] = [dict(id="draft-project", statement=summary,
                         source=dict(kind="tool_result", ref="handoff draft capture"), observed_at=observed_at, confidence="high")]
    c["environment"] = [dict(id="draft-environment",
                             statement="Python " + sys.version.split()[0] + " on " + platform.system() +
                                       ("; git available" if git else "; git unavailable"),
                             source=dict(kind="tool_result", ref="handoff draft capture"), observed_at=observed_at, confidence="high")]
    c["working_copy"] = [dict(id="draft-working",
                              statement="Working layer: %d file entries captured, %d exclusions recorded; details land in evidence/capture.json on save"
                                        % (len(capture["working"]), len(capture["exclusions"])),
                              source=dict(kind="tool_result", ref="handoff draft capture"), observed_at=observed_at, confidence="high")]
    if (root / "AGENTS.md").is_file():
        c["instructions"] = [dict(id="draft-instructions", statement="AGENTS.md exists at the project root; re-read it before acting",
                                  source=dict(kind="file", ref="AGENTS.md"), observed_at=observed_at, confidence="high")]
    for domain in HINTS:
        if domain == "intent":
            continue  # already scaffolded above with intent-specific placeholders
        c[domain] = [placeholder(domain, observed_at)]
    c["coverage"] = {}
    for d in DOMAINS:
        if d == "intent" or d in HINTS:
            c["coverage"][d] = dict(status="unknown", reason="draft placeholder; replace TODO facts from the visible conversation before saving")
        elif d in ("project", "environment", "working_copy") or (d == "instructions" and c["instructions"]):
            c["coverage"][d] = dict(status="partial", reason="draft auto-filled mechanical facts; review before saving")
        elif d == "instructions":
            c["coverage"][d] = dict(status="unknown", reason="no AGENTS.md found at the project root by draft")
        else:
            c["coverage"][d] = dict(status="unknown", reason="draft declares no attachments; add facts if the user supplied files")
    c["schema_version"] = VERSION
    c["observed_fingerprint"] = capture["fingerprint"]
    target = Path(out or "context.draft.json").absolute()
    try:
        write_bytes(target, encoded(c))
    except FileExistsError as exc:
        raise HandoffError("Draft output exists; choose another --out or remove the file first", 4) from exc
    todo = [d for d in DOMAINS if d == "intent" or d in HINTS]
    return result("draft", readiness="not_applicable", draft_path=str(target), todo_domains=todo,
                  code_fingerprint=capture["fingerprint"],
                  warnings=["The draft is scaffolding: save refuses while draft_template facts or TODO statements remain",
                            "Mechanical facts were observed locally; they are not semantic authority"],
                  next_steps=["Replace every TODO fact from the visible conversation, then: save --root <project> --context " + str(target),
                              "Keep coverage honest: unknown with a reason is correct, fabricated is not"])
