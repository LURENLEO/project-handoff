import json
import os
import platform
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .common import HandoffError, REVIEW_GAPS, VERSION, TOOL_VERSION, digest, encoded, fault, no_links, now, read_json, replace, safe_path, sync_dir, write_bytes, result
from .collect import collect
from .context import check_continuity, prepare_context, readiness, render, set_freshness
from .redact import clean
from .validate import verify_snapshot


class Lock:
    def __init__(self, path):
        self.path = path
        self.token = uuid.uuid4().hex

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise HandoffError("Writer lock exists; inspect owner, do not remove by age", 5) from exc
        with os.fdopen(fd, "wb") as f:
            f.write(encoded(dict(token=self.token, pid=os.getpid(), host=socket.gethostname(), created_at=now())))
            f.flush()
            os.fsync(f.fileno())
        return self

    def __exit__(self, *_):
        try:
            if self.path.exists() and read_json(self.path).get("token") == self.token:
                self.path.unlink()
        except OSError:
            pass  # Lock removed externally; release is best-effort and must not mask the result.


def locate(root, store=None, stream="default", create=False):
    root = Path(root).resolve()
    if not root.is_dir():
        raise HandoffError("Project root must exist", 4)
    safe_path(stream)
    if "/" in stream:
        raise HandoffError("stream must be one path component")
    store = no_links(Path(store).absolute() if store else root / ".handoff")
    config_path = store / "config.json"
    if create:
        store.mkdir(parents=True, exist_ok=True)
        with Lock(store / ".config.lock"):
            config = read_json(config_path) if config_path.exists() else dict(schema_version=VERSION, project_id="p-" + uuid.uuid4().hex, workspaces={})
            key = digest(os.fsencode(str(root)))[:20]
            if key not in config["workspaces"]:
                config["workspaces"][key] = dict(workspace_id="w-" + uuid.uuid4().hex[:12], root_hint=str(root))
                temp = store / (".config-" + uuid.uuid4().hex)
                write_bytes(temp, encoded(config))
                replace(temp, config_path)
    elif config_path.exists():
        config = read_json(config_path)
        key = digest(os.fsencode(str(root)))[:20]
    else:
        return store, None, None
    if key not in config["workspaces"]:
        return store, None, None
    wid = config["workspaces"][key]["workspace_id"]
    safe_path(wid)
    identity = dict(project_id=config["project_id"], workspace_id=wid, stream_id=stream)
    folder = no_links(store / "workspaces" / wid / "streams" / stream)
    return store, folder, identity


def save(root, context_path, store=None, stream="default", include_ignored=(), max_file=None):
    return publish(root, read_json(context_path), "save", store, stream, include_ignored, max_file)


def publish(root, raw, operation="save", store=None, stream="default", include_ignored=(), max_file=None,
            allow_semantic_reset=False, warnings=None, next_steps=None):
    root = Path(root).resolve()
    context, redacted = prepare_context(raw)
    store, folder, identity = locate(root, store, stream, create=True)
    with Lock(folder / ".writer.lock"):
        previous, parent = None, None
        current = folder / "CURRENT.json"
        if current.exists():
            _, old, previous, _ = verify_snapshot(current)
            parent = old["snapshot_id"]
        check_continuity(context, previous, allow_semantic_reset)
        sid = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        stage = folder / ".staging" / sid
        stage.mkdir(parents=True)
        write_bytes(stage / "context-draft.json", encoded(context))
        started = now()
        options = dict(include_ignored=include_ignored)
        if max_file is not None:
            options["max_file"] = max_file
        stable = False
        for attempt in range(3):
            before, payloads = collect(root, store, **options)
            after, _ = collect(root, store, **options)
            if before["consistency_token"] == after["consistency_token"]:
                stable = True
                break
        if not stable:
            write_bytes(stage / "unstable.json", encoded(dict(stability="unstable", before=before["fingerprint"], after=after["fingerprint"])))
            raise HandoffError("Workspace changed during all three capture attempts; CURRENT unchanged", 5,
                               {"stability": "unstable", "draft_path": str(stage)})
        capture = before
        fp = capture["fingerprint"]
        set_freshness(context, fp)
        capture_gaps = list(capture["gaps"])
        capture_gaps.extend({"kind": "excluded", **x} for x in capture["exclusions"] if x["required_for_restore"] or x["layer"] in ("baseline", "index"))
        captured_files = {x["path"]: x for x in capture["working"]}
        for asset in context["assets"]:
            p = asset.get("path")
            if p not in captured_files or not captured_files[p].get("payload"):
                capture_gaps.append({"kind": "missing_asset", "id": asset["id"], "reason": "Referenced attachment has no captured byte payload"})
            elif asset.get("sha256") and asset["sha256"] != captured_files[p]["payload"]:
                capture_gaps.append({"kind": "asset_changed", "id": asset["id"], "reason": "Attachment hash differs from semantic observation"})
        if redacted:
            capture_gaps.append({"kind": "redacted_context", "reason": "Sensitive semantic values filtered before persistence; review affected facts"})
        ready, gaps = readiness(context, fp, capture_gaps)
        # Review-only gaps ask for human/agent attention but do not reduce restore capability.
        restore_blockers = [g for g in capture_gaps if g.get("kind") not in REVIEW_GAPS]
        portability = "local_only" if restore_blockers else "self_contained"
        context.update(schema_version=VERSION, snapshot_id=sid, parent_snapshot_id=parent, identity=identity)
        manifest = dict(schema_version=VERSION, tool_version=TOOL_VERSION, snapshot_id=sid, parent_snapshot_id=parent,
                        identity=identity, captured_started_at=started, captured_ended_at=now(), code_fingerprint=fp,
                        stability="double_checked", readiness=ready, portability=portability, exclusions=capture["exclusions"],
                        gaps=gaps, required_capabilities=[], files={}, capture_platform=platform.system(),
                        scope="Declared source and semantic materials; no system environment or external service state")
        summary, next_agent = render(context, manifest)
        files = {"state.json": encoded(context), "SUMMARY.md": summary.encode(), "NEXT_AGENT.md": next_agent.encode(),
                 "evidence/capture.json": encoded(capture)}
        files.update({"payload/" + h: data for h, data in payloads.items()})
        # Draft is already filtered; remove only this transaction's own known file.
        (stage / "context-draft.json").unlink()
        for name, data in files.items():
            write_bytes(stage / name, data)
            manifest["files"][name] = dict(size=len(data), sha256=digest(data), purpose="source_payload" if name.startswith("payload/") else "handoff",
                                           type="file", mode="0644", encoding="binary" if name.startswith("payload/") else "utf-8", original=name.startswith("payload/"))
        write_bytes(stage / "manifest.json", encoded(manifest))
        verify_snapshot(stage)
        fault("before_rename")
        final = folder / "snapshots" / sid
        final.parent.mkdir(parents=True, exist_ok=True)
        replace(stage, final)
        fault("after_rename")
        pointer = dict(schema_version=VERSION, snapshot_id=sid, manifest_sha256=digest(encoded(manifest)))
        temp = folder / (".CURRENT-" + uuid.uuid4().hex)
        write_bytes(temp, encoded(pointer))
        fault("before_pointer")
        replace(temp, current)
        fault("after_pointer")
    return result(operation, integrity="valid", readiness=ready, portability=portability, snapshot_path=str(final),
                  current_path=str(current), gaps=gaps, code_fingerprint=fp,
                  warnings=warnings if warnings is not None else
                  ["Double checking is not an OS snapshot", "Add the handoff store to ignore rules if appropriate; no rules were modified"],
                  next_steps=next_steps if next_steps is not None else
                  ["Give NEXT_AGENT.md and this snapshot to the next agent"])


def inspect(root, store=None, stream="default"):
    store, folder, identity = locate(root, store, stream)
    capture, _ = collect(Path(root).resolve(), store)
    snapshots, orphans, current_id = [], [], None
    if folder and (folder / "CURRENT.json").exists():
        _, m, _, _ = verify_snapshot(folder / "CURRENT.json")
        current_id = m["snapshot_id"]
    if folder and (folder / "snapshots").exists():
        for path in sorted((folder / "snapshots").iterdir()):
            if path.is_dir():
                _, m, _, _ = verify_snapshot(path)
                snapshots.append(dict(snapshot_id=m["snapshot_id"], parent=m["parent_snapshot_id"], readiness=m["readiness"]))
        ancestors = set()
        by_id = {x["snapshot_id"]: x for x in snapshots}
        cursor = current_id
        while cursor and cursor not in ancestors:
            ancestors.add(cursor)
            cursor = by_id.get(cursor, {}).get("parent")
        orphans = [x["snapshot_id"] for x in snapshots if x["snapshot_id"] not in ancestors]
    return result("inspect", integrity="valid" if current_id else "not_checked", identity=identity,
                  code_fingerprint=capture["fingerprint"], snapshots=snapshots, current_snapshot_id=current_id,
                  orphan_snapshots=orphans, capture=capture,
                  available_streams=[p.name for p in folder.parent.iterdir() if p.is_dir()] if folder and folder.parent.exists() else [],
                  incomplete_transactions=[p.name for p in (folder / ".staging").iterdir()] if folder and (folder / ".staging").exists() else [])
