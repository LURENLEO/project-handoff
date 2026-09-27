import base64
import os
import shutil
import stat
from pathlib import Path
from .common import HandoffError, MAX_FILE, MAX_TOTAL, digest, encoded, run_git, safe_source_path
from .redact import clean_text, contains_secret, sensitive_path

SKIP_DIRS = {"node_modules", "__pycache__", ".venv", "venv", ".cache", "dist", "build", ".pytest_cache"}


def fingerprint(capture):
    data = {k: v for k, v in capture.items() if k not in ("objects", "max_file", "fingerprint", "consistency_token")}
    data["exclusions"] = [x for x in data["exclusions"] if x["required_for_restore"] or x["layer"] in ("baseline", "index")]
    if capture["git"]:
        data["git"] = {k: v for k, v in capture["git"].items() if k not in ("index_hash", "status_hash")}
    return digest(encoded(data))


def path_record(raw):
    try:
        return raw.decode("utf-8")
    except UnicodeError:
        return {"encoding": "base64", "bytes": base64.b64encode(raw).decode()}


def git_info(root):
    if not shutil.which("git"):
        if (root / ".git").exists():
            raise HandoffError("Git metadata exists but Git is unavailable", 7)
        return None
    r = run_git(root, "rev-parse", "--show-toplevel", check=False)
    if r.returncode:
        return None
    if Path(os.fsdecode(r.stdout.strip())).resolve() != root:
        raise HandoffError("Use the actual Git workspace root, not a subdirectory", 4)
    return os.fsdecode(run_git(root, "rev-parse", "--absolute-git-dir").stdout.strip())


def collect(root, store=None, include_ignored=(), max_file=MAX_FILE):
    root = Path(root).resolve()
    store = Path(store).resolve() if store else root / ".handoff"
    blobs, exclusions, gaps, objects = {}, [], [], {}
    total = 0

    def exclude(path, reason, layer, required=True):
        exclusions.append({"path": clean_text(path) if isinstance(path, str) else path,
                           "reason": reason, "layer": layer, "required_for_restore": required})

    def allowed(path, layer):
        if not isinstance(path, str):
            exclude(path, "Non-UTF-8 filename requires byte mapping", layer)
            return False
        if any(p.lower() == ".handoff" for p in path.split("/")) or (root / path).is_relative_to(store):
            exclude(path, "Handoff storage excluded to prevent recursive capture", layer, False)
            return False
        try:
            safe_source_path(path)
        except HandoffError as exc:
            exclude(path, str(exc), layer)
            return False
        if sensitive_path(path):
            exclude(path, "High-risk filename", layer)
            return False
        return True

    def payload(data, path, layer):
        nonlocal total
        if contains_secret(data):
            exclude(path, "Possible credential detected; original bytes excluded", layer)
            return None
        h = digest(data)
        if h not in blobs:
            total += len(data)
            if total > MAX_TOTAL:
                raise HandoffError("Capture exceeds total memory limit; narrow declared scope", 4)
            blobs[h] = data
        return h

    def git_object(oid, kind, path):
        if oid in objects:
            return objects[oid]["payload"]
        size = int(run_git(root, "cat-file", "-s", oid).stdout)
        if size > max_file:
            exclude(path, "Object exceeds configured file limit", "git")
            return None
        data = run_git(root, "cat-file", kind, oid).stdout
        h = payload(data, path, "git")
        if h:
            objects[oid] = {"type": kind, "payload": h, "size": len(data)}
        return h

    gitdir = git_info(root)
    git = None
    base, index, work = [], [], []
    paths, tracked = set(), set()
    if gitdir:
        head_result = run_git(root, "rev-parse", "--verify", "HEAD", check=False)
        head = head_result.stdout.decode().strip() if not head_result.returncode else None
        branch_result = run_git(root, "symbolic-ref", "-q", "HEAD", check=False)
        branch = branch_result.stdout.decode().strip() if not branch_result.returncode else None
        operation = []
        for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "sequencer", "BISECT_LOG"):
            if (Path(gitdir) / name).exists():
                operation.append(name)
        index_path = Path(gitdir) / "index"
        index_hash = digest(index_path.read_bytes()) if index_path.exists() else None
        git = dict(head=head, branch=branch, detached=bool(head and not branch), operations=operation,
                   index_hash=index_hash, object_format=run_git(root, "rev-parse", "--show-object-format").stdout.decode().strip())
        if operation:
            gaps.append({"kind": "git_operation", "reason": "Active Git operation; local continuation only, cross-workspace operation restore unsupported"})
        flags = run_git(root, "ls-files", "-v", "-z").stdout.split(b"\0")
        special_flags = [path_record(x[2:]) for x in flags if x and (chr(x[0]).islower() or x[:1] == b"S")]
        if special_flags:
            gaps.append({"kind": "index_flags", "reason": "assume-unchanged/skip-worktree flags cannot be restored", "paths": special_flags})
        git["special_flags"] = special_flags
        if head:
            git_object(head, "commit", "<HEAD commit>")
            root_tree = run_git(root, "rev-parse", "HEAD^{tree}").stdout.decode().strip()
            git["tree"] = root_tree
            git_object(root_tree, "tree", "<root tree>")
            for record in run_git(root, "ls-tree", "-r", "-t", "-z", "HEAD").stdout.split(b"\0"):
                if not record:
                    continue
                meta, raw_path = record.split(b"\t", 1)
                mode, kind, oid = meta.decode().split()
                path = path_record(raw_path)
                if not allowed(path, "baseline"):
                    continue
                if kind == "tree":
                    git_object(oid, kind, path)
                    continue
                item = dict(path=path, mode=mode, oid=oid, kind=kind)
                if kind == "commit":
                    gaps.append({"kind": "submodule", "path": path, "reason": "Submodule registered but not recursively captured"})
                    item["payload"] = None
                else:
                    item["payload"] = git_object(oid, "blob", path)
                base.append(item)
                tracked.add(path)
        for record in run_git(root, "ls-files", "--stage", "-z").stdout.split(b"\0"):
            if not record:
                continue
            meta, raw_path = record.split(b"\t", 1)
            mode, oid, stage = meta.decode().split()
            path = path_record(raw_path)
            if not allowed(path, "index"):
                continue
            tracked.add(path)
            item = dict(path=path, mode=mode, oid=oid, stage=int(stage), payload=None)
            if mode == "160000":
                gaps.append({"kind": "submodule", "path": path, "reason": "Submodule contents not captured"})
            else:
                item["payload"] = git_object(oid, "blob", path)
            if int(stage):
                gaps.append({"kind": "conflict", "path": path, "reason": "Conflict stages retained; operation restore unsupported"})
            index.append(item)
        # Status is captured as facts without executing textconv or external diff.
        git["status_porcelain_b64"] = base64.b64encode(run_git(root, "status", "--porcelain=v2", "-z", "--untracked-files=all").stdout).decode()
        for raw in run_git(root, "ls-files", "--others", "--exclude-standard", "-z").stdout.split(b"\0"):
            if raw:
                path = path_record(raw)
                if allowed(path, "worktree"):
                    paths.add(path)
        paths |= tracked
    else:
        for folder, dirs, files in os.walk(root, followlinks=False):
            directory = Path(folder)
            if directory != root and (directory / ".git").exists():
                gaps.append({"kind": "nested_repository", "path": directory.relative_to(root).as_posix(), "reason": "Nested repository requires separate capture"})
                dirs[:] = []
                continue
            for name in list(dirs):
                p = directory / name
                rel = p.relative_to(root).as_posix()
                if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
                    dirs.remove(name)
                    paths.add(rel)
                elif name in SKIP_DIRS or name in (".git", ".handoff") or p == store:
                    dirs.remove(name)
                    exclude(rel, "Dependency/cache/metadata directory omitted", "worktree", False)
            paths.update((directory / name).relative_to(root).as_posix() for name in files)
    for path in include_ignored:
        safe_source_path(path)
        paths.add(path)
    seen = set()
    for path in sorted(paths):
        if not allowed(path, "worktree"):
            continue
        if path.casefold() in seen:
            exclude(path, "Case-insensitive filename collision", "worktree")
            continue
        seen.add(path.casefold())
        p = root / path
        if any(parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction())
               for parent in p.parents if parent != root and parent.is_relative_to(root)):
            exclude(path, "Ancestor is a link/junction", "worktree")
            continue
        if not p.exists() and not p.is_symlink():
            work.append(dict(path=path, kind="deleted", payload=None, mode=None))
            continue
        st = p.lstat()
        if hasattr(p, "is_junction") and p.is_junction():
            exclude(path, "Windows junction not traversed", "worktree")
            continue
        if stat.S_ISDIR(st.st_mode):
            if (p / ".git").exists():
                gaps.append({"kind": "nested_repository", "path": path, "reason": "Nested repository requires a separate snapshot"})
            continue
        if not (stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode)):
            exclude(path, "Unsupported filesystem object", "worktree")
            continue
        if path not in tracked and any(part in SKIP_DIRS for part in path.split("/")):
            exclude(path, "Untracked dependency/cache/build output omitted", "worktree", False)
            continue
        if st.st_size > max_file:
            exclude(path, "File exceeds configured limit", "worktree")
            continue
        if stat.S_ISLNK(st.st_mode):
            data = os.fsencode(os.readlink(p))
            kind, mode = "symlink", "120000"
            target = os.fsdecode(data)
            try:
                internal_link = (p.parent / target).resolve().is_relative_to(root)
            except (OSError, RuntimeError):
                internal_link = False
            if not internal_link:
                gaps.append({"kind": "external_symlink", "path": path, "reason": "Link target is outside project; not followed, restore blocked"})
        else:
            with p.open("rb") as handle:
                data = handle.read(max_file + 1)
            if len(data) > max_file:
                exclude(path, "File grew beyond configured limit during capture", "worktree")
                continue
            kind, mode = "file", "100755" if st.st_mode & stat.S_IXUSR else "100644"
            if os.name == "nt":
                mode = next((i["mode"] for i in index if i["path"] == path and i["stage"] == 0 and i["mode"] != "120000"), mode)
        h = payload(data, path, "worktree")
        if h:
            work.append(dict(path=path, kind=kind, mode=mode, payload=h, size=len(data)))
            if data.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                gaps.append({"kind": "lfs_pointer", "path": path, "reason": "Only LFS pointer captured; real content unavailable"})
    exclusions = sorted(exclusions, key=lambda x: encoded(x))
    # Do not persist raw porcelain: it can contain sensitive paths excluded above.
    if git:
        git["status_hash"] = digest(base64.b64decode(git.pop("status_porcelain_b64")))
    capture = dict(git=git, baseline=base, index=index, working=work, objects=objects,
                   exclusions=exclusions, gaps=gaps, include_ignored=list(include_ignored), max_file=max_file)
    capture["fingerprint"] = fingerprint(capture)
    capture["consistency_token"] = digest(encoded(capture))
    return capture, blobs
