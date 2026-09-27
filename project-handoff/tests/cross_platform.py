"""Export on one OS and restore on another, preserving Git layers and bytes."""
import argparse
import json
import platform
import tempfile
from pathlib import Path
from fixtures import context
from handoff_core.common import encoded, run_git
from handoff_core.collect import collect
from handoff_core.store import save
from handoff_core.portability import export, restore
from handoff_core.validate import verify_snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit")
    parser.add_argument("--archive")
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="handoff-cross-") as tmp:
        root = Path(tmp) / "project"
        if args.emit:
            root.mkdir()
            run_git(root, "init", "-q")
            run_git(root, "config", "user.name", "Fixture")
            run_git(root, "config", "user.email", "fixture@example.invalid")
            run_git(root, "config", "core.autocrlf", "false")
            (root / "code.txt").write_bytes(b"baseline\r\n")
            run_git(root, "add", "code.txt")
            run_git(root, "commit", "-qm", "Baseline")
            (root / "code.txt").write_bytes(b"staged\r\n")
            run_git(root, "add", "code.txt")
            (root / "code.txt").write_bytes(b"working\r\n")
            (root / "中文.bin").write_bytes(bytes(range(256)))
            ctx = Path(tmp) / "context.json"
            ctx.write_bytes(encoded(context(collect(root)[0]["fingerprint"])))
            saved = save(root, ctx)
            report = export(saved["snapshot_path"], "source", args.emit)
            report["origin_os"] = platform.system()
        else:
            report = restore(args.archive, root, apply=True)
            _, m, _, saved = verify_snapshot(report["snapshot_path"])
            capture, _ = collect(root)
            report["origin_os"] = m["capture_platform"]
            report["target_os"] = platform.system()
            report["fingerprint_equal"] = capture["fingerprint"] == saved["fingerprint"]
            if not report["fingerprint_equal"]:
                raise AssertionError("Restored code fingerprint differs across platforms")
        Path(args.report).write_bytes(encoded(report))
        print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
