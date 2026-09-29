"""Environment and installation self-check with per-client remediation hints."""
import os
import shutil
import sys
from pathlib import Path
from .common import HandoffError, result
from .store import locate
from .validate import verify_snapshot

SKILL_DIRS = ((".agents", "skills"), (".zcode", "skills"), (".claude", "skills"), (".codex", "skills"))
HOST_ENV = {"Claude Code": ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"), "Codex": ("CODEX_HOME",),
            "Cursor": ("CURSOR_TRACE_ID",), "ZCode": ("ZCODE_HOME", "ZCODE_ENTRYPOINT")}
INSTALL_HINT = "Copy the project-handoff folder to ~/.agents/skills/project-handoff (or ~/.zcode/skills/, ~/.claude/skills/, ~/.codex/skills/), then re-run doctor"


def doctor(root=None):
    checks = []

    def check(cid, ok, detail, remediation=None, warn=False):
        checks.append(dict(id=cid, status="ok" if ok else ("warn" if warn else "fail"),
                           detail=detail, remediation=None if ok else remediation))

    check("python", sys.version_info >= (3, 11), "Python " + sys.version.split()[0],
          "Python 3.11+ is required to run scripts/handoff.py")
    git_ok = bool(shutil.which("git"))
    check("git", git_ok, "git is on PATH" if git_ok else "git was not found on PATH",
          "Install Git; capturing or resuming Git projects requires it", warn=not git_ok)
    home = Path.home()
    found = [str(p) for p in (home.joinpath(*parts, "project-handoff", "SKILL.md") for parts in SKILL_DIRS) if p.is_file()]
    check("skill_install", bool(found), ("installed at: " + ", ".join(found)) if found else "SKILL.md not found in user skill directories",
          INSTALL_HINT, warn=not found)
    hosts = sorted(name for name, keys in HOST_ENV.items() if any(os.environ.get(k) for k in keys))
    check("host", True, "detected hosts: " + (", ".join(hosts) if hosts else "unknown (no client environment markers)"))
    if root:
        root = Path(root)
        if not root.is_dir():
            check("root", False, "project root does not exist: " + str(root), "Pass an existing project directory")
        else:
            try:
                store_path, folder, identity = locate(root)
                check("store", True, "store path: " + str(store_path))
            except HandoffError as exc:
                store_path, folder, identity = None, None, None
                check("store", False, "store path problem: " + str(exc), "Check the --store path for links or permission issues")
            if store_path is not None:
                check("store_registered", bool(folder),
                      ("registered workspace: " + str(folder)) if folder else "no store registered for this root yet",
                      "Any save/quick in this project registers the workspace")
                if folder:
                    current = folder / "CURRENT.json"
                    if current.exists():
                        try:
                            snapshot, _, _, _ = verify_snapshot(current)
                            check("current_snapshot", True, "CURRENT resolves to a verified snapshot: " + snapshot.name)
                        except HandoffError as exc:
                            check("current_snapshot", False, "CURRENT/manifest verification failed (exit code %d)" % exc.code,
                                  "Run inspect; do not trust the package until it verifies or a new save supersedes it")
                    else:
                        check("current_snapshot", True, "no CURRENT yet; nothing saved in this stream")
                    locks = [p for p in (folder / ".writer.lock", folder / ".config.lock") if p.exists()]
                    if locks:
                        check("locks", False, "writer/config lock present: " + ", ".join(p.name for p in locks),
                              "Check the pid/host inside the lock file; do not delete by age alone", warn=True)
                    else:
                        check("locks", True, "no stale locks")
                    staging = sorted(p.name for p in (folder / ".staging").iterdir() if p.is_dir()) if (folder / ".staging").exists() else []
                    check("staging", not staging,
                          ("unpublished transactions: " + ", ".join(staging)) if staging else "no unpublished staging transactions",
                          "Run inspect then gc --prune-staging --apply after confirming no writer is active", warn=bool(staging))
    failed = [c["id"] for c in checks if c["status"] == "fail"]
    return result("doctor", readiness="not_applicable", checks=checks, failed=failed,
                  next_steps=[c["remediation"] for c in checks if c["remediation"]] or
                  ["Environment looks usable; run quick or save to create the first handoff"])
