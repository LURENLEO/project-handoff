"""Low-friction one-command handoff: full state capture with an honestly minimal semantic layer."""
from .common import HandoffError, VERSION, now
from .context import DOMAINS
from .store import publish


def quick_context(note, observed_at):
    c = {d: [] for d in DOMAINS}
    c["intent"] = dict(id="quick-intent", statement=note, source=dict(kind="user_message", ref="quick save --note argument"),
                       observed_at=observed_at, confidence="high",
                       original_goal=note, current_goal=note, acceptance=[], scope=[], non_goals=[], corrections=[])
    c["schema_version"] = VERSION
    c["observed_fingerprint"] = None
    c["coverage"] = {d: dict(status="unknown", reason="quick save: semantics not captured; run draft or a full save for a richer handoff")
                     for d in DOMAINS}
    c["coverage"]["intent"] = dict(status="partial", reason="quick save: only the caller note is captured; acceptance and scope are missing")
    return c


def quick(root, note, store=None, stream="default", include_ignored=(), max_file=None):
    note = (note or "").strip()
    if not note:
        raise HandoffError("--note is required and must not be empty", 2)
    return publish(root, quick_context(note, now()), "quick", store, stream, include_ignored, max_file,
                   allow_semantic_reset=True,
                   warnings=["Semantic coverage is unknown by design; readiness stays conditional",
                             "Double checking is not an OS snapshot",
                             "Add the handoff store to ignore rules if appropriate; no rules were modified"],
                   next_steps=["Semantic domains were not captured: run draft + save before the next major handoff",
                               "Give NEXT_AGENT.md and this snapshot to the next agent"])
