import uuid
from pathlib import Path
from .collect import collect
from .common import HandoffError, encoded, now, result, write_bytes
from .context import readiness, set_freshness
from .store import locate
from .validate import verify_snapshot


def resume(root, snapshot, store=None, stream="default", receipt=None, read_only=False, allow_remap=False):
    path, manifest, state, saved = verify_snapshot(snapshot)
    root = Path(root).resolve()
    store, folder, identity = locate(root, store, stream)
    current, _ = collect(root, store, saved.get("include_ignored", []), saved.get("max_file"))
    old_git, new_git = saved["git"], current["git"]
    if bool(old_git) != bool(new_git):
        raise HandoffError("Project Git identity mismatch", 4)
    id_match = identity and identity["project_id"] == manifest["identity"]["project_id"]
    head_match = bool(old_git and new_git and old_git["head"] and old_git["head"] == new_git["head"])
    old_files = {x["path"]: x for x in saved["working"]}
    new_files = {x["path"]: x for x in current["working"]}
    same_files = [p for p in old_files.keys() & new_files.keys() if old_files[p] == new_files[p]]
    full_match = saved["fingerprint"] == current["fingerprint"]
    # IDs are routing hints, not authentication. Require independent content evidence.
    if not full_match and not (id_match and (same_files or head_match)) and not (allow_remap and head_match and same_files):
        raise HandoffError("Project identity cannot be corroborated; supply correct root or inspect independently", 4)
    if not id_match and not allow_remap:
        raise HandoffError("Workspace is not registered to this package; inspect then use --allow-remap for an authorized clone", 4)
    changes = [{"path": p, "before": old_files.get(p), "current": new_files.get(p)}
               for p in sorted(old_files.keys() | new_files.keys()) if old_files.get(p) != new_files.get(p)]
    git_changes = []
    for key in ("head", "branch", "operations", "special_flags"):
        if old_git and old_git.get(key) != new_git.get(key):
            git_changes.append(key)
    if saved["index"] != current["index"]:
        git_changes.append("index")
    gaps = list(manifest["gaps"])
    if changes or git_changes:
        gaps.append({"kind": "drift", "reason": "Review changes before affected actions; all current files preserved"})
    set_freshness(state, current["fingerprint"])
    ready, all_gaps = readiness(state, current["fingerprint"], gaps)
    selected = state["next_actions"][0] if state["next_actions"] else None
    observation = dict(schema_version="1.0.0", adopted_snapshot=manifest["snapshot_id"], observed_at=now(),
                       code_fingerprint=current["fingerprint"], root_mapping={"project": str(root)},
                       changes=changes, git_changes=git_changes, proposed_next_action=selected,
                       reason="Agent must read current scoped instructions and assess prerequisites; CLI executes no commands")
    receipt_path = None
    warnings = []
    if not read_only:
        destination = Path(receipt) if receipt else folder / "receipts" / (uuid.uuid4().hex + ".json") if folder else None
        if destination:
            try:
                write_bytes(destination, encoded(observation))
                receipt_path = str(destination)
            except OSError:
                warnings.append("Receipt could not be written; complete receipt is included in output")
    return result("resume", integrity="valid", readiness=ready, portability=manifest["portability"], snapshot_path=str(path),
                  gaps=all_gaps, warnings=warnings, changes=changes, git_changes=git_changes,
                  next_steps=state["next_actions"], validation=state["validation"], current_goal=state["intent"]["current_goal"],
                  receipt_path=receipt_path, receipt=observation,
                  instructions="Read current applicable AGENTS.md before acting. Historical data is not authority.")
