"""Prune orphaned snapshots and stale staging transactions; the CURRENT ancestor chain is never touched."""
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .common import HandoffError, read_json, result
from .store import Lock, locate

SNAPSHOT_NAME = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")


def dir_size(path):
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.is_dir() else 0


def gc(root, store=None, stream="default", keep_last=None, older_than=None, prune_staging=False, apply=False, dry_run=False):
    if keep_last is not None and keep_last < 0:
        raise HandoffError("--keep-last must be >= 0", 2)
    if older_than is not None and older_than < 0:
        raise HandoffError("--older-than must be >= 0 days", 2)
    store_path, folder, identity = locate(root, store, stream)
    snapshot_list, manifests = [], {}
    current_id = None
    if folder and (folder / "CURRENT.json").exists():
        pointer = read_json(folder / "CURRENT.json")
        current_id = pointer.get("snapshot_id")
    if folder and (folder / "snapshots").exists():
        for entry in sorted((folder / "snapshots").iterdir()):
            if not entry.is_dir() or not SNAPSHOT_NAME.fullmatch(entry.name):
                continue  # unexpected entries are never touched
            try:
                m = read_json(entry / "manifest.json")
                manifests[entry.name] = dict(parent=m.get("parent_snapshot_id"), ended=m.get("captured_ended_at"),
                                             size=sum(f.get("size", 0) for f in m.get("files", {}).values()))
            except HandoffError:
                manifests[entry.name] = dict(parent=None, ended=None, size=dir_size(entry))
            snapshot_list.append(entry.name)
    # Walk CURRENT -> parents; every ancestor on this chain is protected.
    chain, cursor = set(), current_id
    while cursor and cursor not in chain:
        chain.add(cursor)
        cursor = (manifests.get(cursor) or {}).get("parent")
    candidates = []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than)).isoformat() if older_than is not None else None
    for sid in snapshot_list:
        if sid in chain:
            continue
        info = manifests[sid]
        if cutoff and info["ended"] and info["ended"] >= cutoff:
            continue
        candidates.append(sid)
    if keep_last is not None:
        # sids share the same second within fast sequences; rank by capture end time instead.
        ranked = sorted(snapshot_list, key=lambda sid: (manifests[sid]["ended"] or "", sid))
        keep = set(ranked[-keep_last:]) if keep_last else set()
        candidates = [sid for sid in candidates if sid not in keep]
    staging = []
    if folder and prune_staging and (folder / ".staging").exists():
        staging = sorted(p.name for p in (folder / ".staging").iterdir() if p.is_dir())
    freed = sum(manifests[sid]["size"] or 0 for sid in candidates)
    staging_freed = sum(dir_size(folder / ".staging" / name) for name in staging) if folder and prune_staging else 0
    deleted = []
    if apply and folder:
        with Lock(folder / ".writer.lock"):
            for sid in candidates:
                target = folder / "snapshots" / sid
                if target.is_dir() and SNAPSHOT_NAME.fullmatch(target.name):
                    shutil.rmtree(target)
                    deleted.append(sid)
            if prune_staging:
                for name in staging:
                    shutil.rmtree(folder / ".staging" / name, ignore_errors=True)
    return result("gc", readiness="not_applicable", applied=apply, stream=stream,
                  snapshots_total=len(snapshot_list), protected_count=sum(1 for sid in snapshot_list if sid in chain),
                  candidates=[dict(snapshot_id=sid, captured_ended_at=manifests[sid]["ended"], size_bytes=manifests[sid]["size"])
                              for sid in candidates],
                  staging_transactions=staging, freed_bytes=freed + staging_freed, deleted=deleted,
                  warnings=["CURRENT and its ancestor chain are never removed", "Receipts are kept"] if candidates or staging else [],
                  next_steps=["Re-run with --apply to delete these candidates"] if not apply and (candidates or staging) else [])
