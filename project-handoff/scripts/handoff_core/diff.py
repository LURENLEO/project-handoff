"""Read-only drift observation between a snapshot and the current workspace."""
from pathlib import Path
from .collect import collect
from .common import HandoffError, result
from .store import locate
from .validate import verify_snapshot


def drift(saved, current):
    """Structural drift between two captures: file changes and Git-level changes."""
    old_files = {x["path"]: x for x in saved["working"]}
    new_files = {x["path"]: x for x in current["working"]}
    changes = [{"path": p, "before": old_files.get(p), "current": new_files.get(p)}
               for p in sorted(old_files.keys() | new_files.keys()) if old_files.get(p) != new_files.get(p)]
    git_changes = []
    old_git, new_git = saved["git"], current["git"]
    for key in ("head", "branch", "operations", "special_flags"):
        if old_git and old_git.get(key) != new_git.get(key):
            git_changes.append(key)
    if saved["index"] != current["index"]:
        git_changes.append("index")
    return changes, git_changes


def diff(snapshot, root, store=None, stream="default", limit=200):
    path, manifest, state, saved = verify_snapshot(snapshot)
    root = Path(root).resolve()
    store_path, folder, identity = locate(root, store, stream)
    current, _ = collect(root, store_path, saved.get("include_ignored", []), saved.get("max_file"))
    if bool(saved["git"]) != bool(current["git"]):
        raise HandoffError("Project Git identity mismatch", 4)
    changes, git_changes = drift(saved, current)
    warnings = []
    # Identity is not corroborated here; diff never writes receipts or proposes authority.
    if not (identity and identity["project_id"] == manifest["identity"]["project_id"]):
        warnings.append("Workspace identity was not corroborated; this is a read-only observation, not a resume")
    truncated = len(changes) > limit
    return result("diff", readiness="not_applicable", snapshot_path=str(path),
                  changes=changes[:limit], git_changes=git_changes, change_count=len(changes),
                  truncated=truncated, limit=limit,
                  saved_fingerprint=saved["fingerprint"], current_fingerprint=current["fingerprint"],
                  identical=not changes and not git_changes,
                  gaps=list(manifest["gaps"]), warnings=warnings,
                  next_steps=["Use resume to corroborate identity and continue authorized work"] if changes or git_changes
                  else ["No drift; resume when ready"])
