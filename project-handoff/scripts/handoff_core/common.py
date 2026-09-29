import hashlib
import json
import os
import re
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

VERSION = "1.0.0"
TOOL_VERSION = "1.1.0"
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_FILES = 20000
# Gap kinds that ask for review but do not by themselves reduce restore capability.
REVIEW_GAPS = {"secret_suspicious", "secret_allowlisted"}


class HandoffError(Exception):
    def __init__(self, message, code=2, details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode()


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise HandoffError("Invalid JSON document", 2) from exc


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r"1\.\d+\.\d+", value):
        raise HandoffError("Unsupported protocol version", 7)


def safe_path(value):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise HandoffError("Unsafe logical path", 3)
    parts = value.split("/")
    if any(p in ("", ".", "..") for p in parts) or PurePosixPath(value).is_absolute():
        raise HandoffError("Unsafe logical path", 3)
    for part in parts:
        if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in part):
            raise HandoffError("Path requires unsupported byte-name mapping", 7)
        if re.search(r'[<>:"|?*]', part) or part.endswith((" ", ".")):
            raise HandoffError("Path is not portable to Windows", 7)
        if re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part):
            raise HandoffError("Reserved device path", 3)
    return value


def safe_source_path(value):
    safe_path(value)
    if any(p.lower() in (".git", ".handoff") for p in value.split("/")):
        raise HandoffError("Reserved project metadata path", 3)
    return value


def no_links(path):
    path = Path(path).absolute()
    for p in (path, *path.parents):
        if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
            raise HandoffError("Link/junction in storage or target path", 4)
    return path


def run_git(root, *args, data=None, check=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    cmd = ["git", "-c", "core.fsmonitor=false"]
    if os.name != "nt":
        # /dev/null is a POSIX path; hooks are never invoked by capture/restore anyway.
        cmd += ["-c", "core.hooksPath=/dev/null"]
    cmd += ["-C", str(root), *args]
    try:
        result = subprocess.run(cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    except FileNotFoundError as exc:
        raise HandoffError("Git is required for this operation", 7) from exc
    if check and result.returncode:
        # Git stderr can contain URLs, credentials or paths; never echo it.
        raise HandoffError("Git operation failed: " + args[0], 4)
    return result


def write_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as f:
        f.write(data)
        fault("write")
        f.flush()
        os.fsync(f.fileno())
        fault("flush")
    sync_dir(path.parent)


def sync_dir(path):
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def replace(src, dst):
    for attempt in range(4):
        try:
            os.replace(src, dst)
            sync_dir(Path(dst).parent)
            return
        except PermissionError:
            if attempt == 3:
                raise
            time.sleep(0.05 * (attempt + 1))


def fault(point):
    # Test-only fault injection; no project/package data can enable this.
    if os.environ.get("HANDOFF_TEST_CRASH") == point:
        os._exit(99)
    if os.environ.get("HANDOFF_TEST_FAULT") == point:
        raise HandoffError("Injected failure at " + point, 6)


def result(operation, **kwargs):
    value = dict(operation=operation, outcome="completed", integrity="not_checked",
                 readiness="conditional", portability="local_only", snapshot_path=None,
                 warnings=[], gaps=[], next_steps=[])
    value.update(kwargs)
    return value
