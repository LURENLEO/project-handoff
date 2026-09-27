import hashlib
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path
from .common import HandoffError, MAX_FILE, MAX_FILES, MAX_TOTAL, VERSION, digest, encoded, no_links, read_json, replace, result, run_git, safe_path, safe_source_path, write_bytes
from .store import locate
from .validate import verify_snapshot


def blockers(capture):
    found = [x for x in capture["exclusions"] if x["required_for_restore"] or x["layer"] in ("baseline", "index")]
    found += capture["gaps"]
    git = capture["git"]
    if git and git.get("object_format") != "sha1":
        found.append({"reason": "Git SHA-256 restoration not supported in 1.0"})
    if git and git.get("head") and git["head"] not in capture["objects"]:
        found.append({"reason": "HEAD object was excluded"})
    return found


def export(snapshot, mode, output):
    path, m, state, capture = verify_snapshot(snapshot)
    output = no_links(Path(output).absolute())
    if output.exists() or output.is_relative_to(path):
        raise HandoffError("Export requires a new file outside the immutable snapshot", 4)
    blocked = blockers(capture) + [g for g in m["gaps"] if g.get("kind") in ("missing_asset", "asset_changed")]
    if mode == "baseline" and not capture["git"]:
        raise HandoffError("Baseline mode requires Git; use source mode", 4)
    # Retain the immutable snapshot verbatim in both modes. Baseline mode intentionally
    # declares a prerequisite and verifies it during restore; source mode needs none.
    envelope = dict(schema_version=VERSION, mode=mode, manifest_sha256=digest((path / "manifest.json").read_bytes()),
                    baseline=capture["git"]["head"] if capture["git"] else None,
                    restore_supported=not blocked, blockers=blocked,
                    portability="local_only" if blocked else "portable_with_prerequisites" if mode == "baseline" else "self_contained")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.parent / ("." + output.name + "." + uuid.uuid4().hex)
    try:
        # Stored entries cannot make our own valid export fail bomb-ratio checks.
        with zipfile.ZipFile(temp, "x", zipfile.ZIP_STORED) as archive:
            archive.writestr("EXPORT.json", encoded(envelope))
            for name in ["manifest.json", *m["files"]]:
                archive.writestr("snapshot/" + name, (path / name).read_bytes())
        with temp.open("r+b") as f:
            os.fsync(f.fileno())
        replace(temp, output)
    finally:
        if temp.exists():
            temp.unlink()
    return result("export", integrity="valid", readiness=m["readiness"], portability=envelope["portability"],
                  snapshot_path=str(path), archive_path=str(output), archive_sha256=digest(output.read_bytes()),
                  gaps=blocked, restore_supported=not blocked,
                  warnings=["Baseline mode retains full snapshot payloads for auditability; it is not a minimal delta"] if mode == "baseline" else [])


def unpack(archive_path, destination):
    try:
        archive = zipfile.ZipFile(archive_path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise HandoffError("Cannot read archive", 3) from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_FILES:
            raise HandoffError("Archive file count exceeds limit", 3)
        total, seen = 0, set()
        for entry in infos:
            name = safe_path(entry.filename)
            if not (name == "EXPORT.json" or name.startswith("snapshot/")):
                raise HandoffError("Unexpected archive namespace", 3)
            mode = entry.external_attr >> 16
            if entry.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
                raise HandoffError("Archive links/special entries forbidden", 3)
            if name.casefold() in seen:
                raise HandoffError("Archive path collision", 3)
            seen.add(name.casefold())
            total += entry.file_size
            if entry.file_size > MAX_FILE or total > MAX_TOTAL or entry.file_size > max(entry.compress_size, 1) * 1000:
                raise HandoffError("Archive size/compression limit exceeded", 3)
        # Only after validating the complete central directory, write to private temp.
        for entry in infos:
            try:
                data = archive.read(entry)
            except (zipfile.BadZipFile, RuntimeError) as exc:
                raise HandoffError("Corrupt/encrypted archive member", 3) from exc
            if len(data) != entry.file_size:
                raise HandoffError("Archive member size mismatch", 3)
            write_bytes(destination / entry.filename, data)
    envelope = read_json(destination / "EXPORT.json")
    from .common import version
    version(envelope.get("schema_version"))
    if envelope.get("mode") not in ("source", "baseline"):
        raise HandoffError("Unknown export mode", 7)
    snapshot, m, state, capture = verify_snapshot(destination / "snapshot")
    if digest((snapshot / "manifest.json").read_bytes()) != envelope.get("manifest_sha256"):
        raise HandoffError("Export manifest hash mismatch", 3)
    if envelope.get("baseline") != (capture["git"]["head"] if capture["git"] else None):
        raise HandoffError("Export baseline mismatch", 3)
    return snapshot, m, state, capture, envelope


def check_paths(capture, snapshot):
    paths = {}
    for layer in ("baseline", "index", "working"):
        for entry in capture[layer]:
            name = safe_source_path(entry["path"])
            if name.casefold() in paths and paths[name.casefold()] != name:
                raise HandoffError("Case collision across layers", 4)
            paths[name.casefold()] = name
    live = {x["path"]: x for x in capture["working"] if x["kind"] != "deleted"}
    for name, item in live.items():
        for parent in Path(name).parents:
            if parent.as_posix() in live:
                raise HandoffError("File/link ancestor conflicts with another path", 4)
        if item["kind"] == "symlink":
            data = (snapshot / "payload" / item["payload"]).read_bytes()
            try:
                target = data.decode("utf-8")
            except UnicodeError as exc:
                raise HandoffError("Unsupported symlink byte target", 7) from exc
            if os.name == "nt":
                raise HandoffError("Windows symlink restore requires separate privilege/capability support", 7)
            if "\\" in target or ":" in target or target.startswith("/"):
                raise HandoffError("Unsafe symlink target", 3)
            depth = len(Path(name).parts) - 1
            for part in target.split("/"):
                depth += -1 if part == ".." else 0 if part in ("", ".") else 1
                if depth < 0:
                    raise HandoffError("Symlink target escapes project", 3)


def baseline_check(capture, baseline):
    if not baseline:
        raise HandoffError("Baseline archive requires --baseline <local-repository>; obtain exact objects yourself, no fetch is performed", 4)
    baseline = Path(baseline).resolve()
    for oid, item in capture["objects"].items():
        # Index-only blobs need not be in baseline repository.
        baseline_oids = {x["oid"] for x in capture["baseline"]}
        if item["type"] in ("commit", "tree") or oid in baseline_oids:
            data = run_git(baseline, "cat-file", item["type"], oid).stdout
            if digest(data) != item["payload"]:
                raise HandoffError("Baseline object mismatch", 4)


def materialize(snapshot, capture, destination):
    git = capture["git"]
    if git:
        run_git(destination, "init", "--quiet")
        run_git(destination, "config", "core.autocrlf", "false")
        run_git(destination, "config", "core.filemode", "false" if os.name == "nt" else "true")
        for oid, obj in capture["objects"].items():
            data = (snapshot / "payload" / obj["payload"]).read_bytes()
            actual = run_git(destination, "hash-object", "-t", obj["type"], "-w", "--stdin", data=data).stdout.decode().strip()
            if actual != oid:
                raise HandoffError("Restored Git object differs", 3)
        branch = git["branch"]
        if branch:
            if not branch.startswith("refs/heads/") or run_git(destination, "check-ref-format", branch, check=False).returncode:
                raise HandoffError("Unsafe Git branch reference", 3)
            run_git(destination, "symbolic-ref", "HEAD", branch)
        if git["head"]:
            # The original commit is preserved; parents are an explicit shallow boundary.
            write_bytes(destination / ".git" / "shallow", (git["head"] + "\n").encode())
            if branch:
                run_git(destination, "update-ref", branch, git["head"])
            else:
                run_git(destination, "update-ref", "--no-deref", "HEAD", git["head"])
        run_git(destination, "read-tree", "--empty")
        entries = b"".join((f'{e["mode"]} {e["oid"]} {e["stage"]}\t' + e["path"]).encode("utf-8") + b"\0" for e in capture["index"])
        if entries:
            run_git(destination, "update-index", "-z", "--index-info", data=entries)
    for item in capture["working"]:
        if item["kind"] == "deleted":
            continue
        p = destination / item["path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        data = (snapshot / "payload" / item["payload"]).read_bytes()
        if item["kind"] == "symlink":
            os.symlink(os.fsdecode(data), p)
        else:
            write_bytes(p, data)
            if os.name != "nt":
                p.chmod(0o755 if item["mode"] == "100755" else 0o644)
        actual = os.fsencode(os.readlink(p)) if p.is_symlink() else p.read_bytes()
        if digest(actual) != item["payload"]:
            raise HandoffError("Restored working bytes differ", 3)
    if git:
        actual = run_git(destination, "ls-files", "--stage", "-z").stdout
        if actual != entries:
            raise HandoffError("Restored index differs", 3)
        if git["head"] and run_git(destination, "rev-parse", "HEAD").stdout.decode().strip() != git["head"]:
            raise HandoffError("Restored HEAD differs", 3)
        branch_result = run_git(destination, "symbolic-ref", "-q", "HEAD", check=False)
        actual_branch = branch_result.stdout.decode().strip() if branch_result.returncode == 0 else None
        if actual_branch != git["branch"]:
            raise HandoffError("Restored branch/detached state differs", 3)


def restore(archive, target, apply=False, baseline=None):
    target = no_links(Path(target).absolute())
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise HandoffError("Restore target must be absent or empty; existing work is never overwritten", 4)
    with tempfile.TemporaryDirectory(prefix="handoff-verify-") as temp:
        snapshot, m, state, capture, envelope = unpack(archive, Path(temp))
        blocked = blockers(capture) + [g for g in m["gaps"] if g.get("kind") in ("missing_asset", "asset_changed")]
        if blocked or not envelope.get("restore_supported"):
            raise HandoffError("Package does not support complete restore", 4, {"gaps": blocked})
        check_paths(capture, snapshot)
        if envelope["mode"] == "baseline":
            baseline_check(capture, baseline)
        plan = dict(target=str(target), files=len(capture["working"]), index_entries=len(capture["index"]),
                    head=capture["git"]["head"] if capture["git"] else None,
                    mode=envelope["mode"], history="HEAD preserved as shallow boundary; no full history")
        if not apply:
            return result("restore", outcome="planned", integrity="valid", readiness=m["readiness"],
                          portability=envelope["portability"], plan=plan, gaps=m["gaps"])
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".handoff-restore-", dir=target.parent))
        try:
            materialize(snapshot, capture, staging)
            # Register identity at the final root, not the temporary staging path.
            from .common import now
            identity = m["identity"]
            wid = "w-" + uuid.uuid4().hex[:12]
            store = staging / ".handoff"
            config = dict(schema_version=VERSION, project_id=identity["project_id"], workspaces={
                digest(os.fsencode(str(target.resolve())))[:20]: dict(workspace_id=wid, root_hint=str(target))})
            write_bytes(store / "config.json", encoded(config))
            stream = safe_path(identity["stream_id"])
            if "/" in stream:
                raise HandoffError("Invalid stream ID", 3)
            folder = store / "workspaces" / wid / "streams" / stream
            dest = folder / "snapshots" / safe_path(m["snapshot_id"])
            shutil.copytree(snapshot, dest)
            write_bytes(folder / "CURRENT.json", encoded(dict(schema_version=VERSION, snapshot_id=m["snapshot_id"], manifest_sha256=envelope["manifest_sha256"])))
            if target.exists():
                # rmdir succeeds only while still empty; never recursively delete a target.
                target.rmdir()
            os.rename(staging, target)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return result("restore", integrity="valid", readiness=m["readiness"], portability=envelope["portability"],
                      snapshot_path=str(target / dest.relative_to(staging)), plan=plan, gaps=m["gaps"],
                      verified_layers=["HEAD", "index", "working_bytes"] if capture["git"] else ["working_bytes"],
                      warnings=["System dependencies, external services and full Git history are outside the restored scope"])
