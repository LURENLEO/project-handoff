import hashlib
from pathlib import Path
from .common import HandoffError, MAX_FILE, MAX_FILES, MAX_TOTAL, digest, read_json, safe_path, safe_source_path, version, no_links
from .context import validate_context


def resolve_snapshot(path):
    path = no_links(Path(path).absolute())
    expected = None
    if path.is_file():
        pointer = read_json(path)
        version(pointer.get("schema_version"))
        sid = pointer.get("snapshot_id")
        safe_path(sid)
        if "/" in sid:
            raise HandoffError("Invalid snapshot ID in CURRENT", 3)
        expected = pointer.get("manifest_sha256")
        path = no_links(path.parent / "snapshots" / sid)
    return path, expected


def verify_snapshot(path):
    path, expected = resolve_snapshot(path)
    try:
        raw = (path / "manifest.json").read_bytes()
        if expected and digest(raw) != expected:
            raise HandoffError("CURRENT manifest hash mismatch", 3)
        if len(raw) > MAX_FILE:
            raise HandoffError("Manifest exceeds size limit", 3)
        m = read_json(path / "manifest.json")
        version(m.get("schema_version"))
        if m.get("required_capabilities", []) != []:
            raise HandoffError("Unknown required capability", 7)
        for key in ("snapshot_id", "identity", "files", "code_fingerprint", "stability", "exclusions", "gaps", "readiness", "portability"):
            if key not in m:
                raise HandoffError("Incomplete manifest: " + key, 3)
        for value in [m["snapshot_id"], *[m["identity"][k] for k in ("project_id", "workspace_id", "stream_id")]]:
            safe_path(value)
            if "/" in value:
                raise HandoffError("Identity IDs must be single components", 3)
        if m["stability"] != "double_checked" or m["readiness"] not in ("ready", "conditional", "blocked") or m["portability"] not in ("local_only", "portable_with_prerequisites", "self_contained"):
            raise HandoffError("Invalid capability declaration", 3)
        if not isinstance(m["files"], dict) or len(m["files"]) > MAX_FILES:
            raise HandoffError("Invalid file table", 3)
        required = {"state.json", "SUMMARY.md", "NEXT_AGENT.md", "evidence/capture.json"}
        if not required <= m["files"].keys():
            raise HandoffError("Required package files missing", 3)
        seen, total = set(), 0
        for name, entry in m["files"].items():
            safe_path(name)
            if name == "manifest.json" or name.casefold() in seen:
                raise HandoffError("Duplicate/reserved package path", 3)
            seen.add(name.casefold())
            p = no_links(path / name)
            if not p.is_file():
                raise HandoffError("Package file missing", 3)
            size = p.stat().st_size
            total += size
            if size > MAX_FILE or total > MAX_TOTAL or size != entry.get("size"):
                raise HandoffError("Package size mismatch/limit", 3)
            if digest(p.read_bytes()) != entry.get("sha256"):
                raise HandoffError("Package file hash mismatch", 3)
        actual = {p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file() or p.is_symlink()}
        if actual != set(m["files"]) | {"manifest.json"}:
            raise HandoffError("Unexpected unlisted package files", 3)
        state = read_json(path / "state.json")
        try:
            validate_context(state)
        except HandoffError as exc:
            if exc.code == 7:
                raise
            raise HandoffError("Invalid semantic state: " + str(exc), 3) from exc
        for key in ("snapshot_id", "identity", "parent_snapshot_id"):
            if state.get(key) != m.get(key):
                raise HandoffError("State/manifest identity mismatch", 3)
        capture = read_json(path / "evidence/capture.json")
        from .collect import fingerprint
        if capture.get("fingerprint") != m["code_fingerprint"] or fingerprint(capture) != capture["fingerprint"]:
            raise HandoffError("Capture fingerprint mismatch", 3)
        refs = []
        for layer in ("baseline", "index", "working"):
            if not isinstance(capture.get(layer), list):
                raise HandoffError("Missing capture layer", 3)
            keys = set()
            for item in capture[layer]:
                safe_source_path(item["path"])
                if layer == "working" and item.get("kind") not in ("file", "symlink", "deleted"):
                    raise HandoffError("Invalid working file kind", 3)
                if layer == "index" and item.get("stage") not in (0, 1, 2, 3):
                    raise HandoffError("Invalid index stage", 3)
                key = (item["path"].casefold(), item.get("stage", 0))
                if key in keys:
                    raise HandoffError("Duplicate/colliding capture path", 3)
                keys.add(key)
                if item.get("payload"):
                    refs.append(item["payload"])
                    if layer in ("baseline", "index") and capture["objects"].get(item.get("oid"), {}).get("payload") != item["payload"]:
                        raise HandoffError("Git layer/object reference mismatch", 3)
                    if layer == "working" and m["files"].get("payload/" + item["payload"], {}).get("size") != item.get("size"):
                        raise HandoffError("Working payload size mismatch", 3)
                if item.get("mode") not in (None, "100644", "100755", "120000", "160000"):
                    raise HandoffError("Unsupported file mode", 7)
        for oid, item in capture.get("objects", {}).items():
            h = item["payload"]
            refs.append(h)
            if not isinstance(h, str) or len(h) != 64 or any(x not in "0123456789abcdef" for x in h):
                raise HandoffError("Invalid object payload reference", 3)
            if item["type"] not in ("blob", "tree", "commit"):
                raise HandoffError("Unsupported Git object type", 7)
            data = (path / "payload" / h).read_bytes() if len(h) == 64 and all(x in "0123456789abcdef" for x in h) else b""
            object_data = (item["type"] + " " + str(len(data))).encode() + b"\0" + data
            algorithm = hashlib.sha256 if len(oid) == 64 else hashlib.sha1
            if algorithm(object_data).hexdigest() != oid:
                raise HandoffError("Git object hash mismatch", 3)
        for ref in refs:
            if not isinstance(ref, str) or len(ref) != 64 or any(c not in "0123456789abcdef" for c in ref):
                raise HandoffError("Invalid payload reference", 3)
            name = "payload/" + ref
            if name not in m["files"] or m["files"][name]["sha256"] != ref:
                raise HandoffError("Broken payload reference", 3)
        return path, m, state, capture
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        raise HandoffError("Malformed or incomplete package", 3) from exc
