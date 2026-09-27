#!/usr/bin/env python3
"""Project handoff CLI. stdout contains one JSON document, never project commands."""
import argparse
import json
import sys
from handoff_core.common import HandoffError, MAX_FILE, result
from handoff_core.redact import clean


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise HandoffError(message, 2)


def parser():
    p = Parser(description=__doc__)
    sub = p.add_subparsers(dest="operation", required=True)
    for mode in ("save", "inspect", "resume"):
        cmd = sub.add_parser(mode)
        cmd.add_argument("--root", required=True)
        cmd.add_argument("--store")
        cmd.add_argument("--stream", default="default")
        if mode == "save":
            cmd.add_argument("--context", required=True, dest="context_path")
            cmd.add_argument("--include-ignored", action="append", default=[], dest="include_ignored")
            cmd.add_argument("--max-file", type=int, default=MAX_FILE, dest="max_file")
        if mode == "resume":
            cmd.add_argument("--snapshot", required=True)
            cmd.add_argument("--receipt")
            cmd.add_argument("--read-only", action="store_true", dest="read_only")
            cmd.add_argument("--allow-remap", action="store_true", dest="allow_remap")
    cmd = sub.add_parser("verify")
    cmd.add_argument("--snapshot", required=True)
    cmd = sub.add_parser("export")
    cmd.add_argument("--snapshot", required=True)
    cmd.add_argument("--mode", choices=("baseline", "source"), required=True)
    cmd.add_argument("--output", required=True)
    cmd = sub.add_parser("restore")
    cmd.add_argument("--archive", required=True)
    cmd.add_argument("--target", required=True)
    cmd.add_argument("--baseline")
    intent = cmd.add_mutually_exclusive_group(required=True)
    intent.add_argument("--apply", action="store_true")
    intent.add_argument("--dry-run", action="store_true", dest="dry_run")
    return p


def main(argv=None):
    operation = "unknown"
    try:
        args = vars(parser().parse_args(argv))
        operation = args.pop("operation")
        args.pop("dry_run", None)
        if operation == "save":
            from handoff_core.store import save
            if not 1 <= args["max_file"] <= MAX_FILE:
                raise HandoffError("--max-file must be between 1 and 67108864 bytes")
            output = save(**args)
        elif operation == "inspect":
            from handoff_core.store import inspect
            output = inspect(**args)
        elif operation == "verify":
            from handoff_core.validate import verify_snapshot
            path, m, _, _ = verify_snapshot(args["snapshot"])
            output = result(operation, integrity="valid", readiness=m["readiness"], portability=m["portability"],
                            snapshot_path=str(path), gaps=m["gaps"], warnings=["Integrity hashes are not source authentication"])
        elif operation == "resume":
            from handoff_core.resume import resume
            output = resume(**args)
        elif operation == "export":
            from handoff_core.portability import export
            output = export(**args)
        else:
            from handoff_core.portability import restore
            output = restore(**args)
        code = 0
    except HandoffError as exc:
        code = exc.code
        output = result(operation, outcome="failed", integrity="invalid" if code == 3 else "not_checked", readiness="blocked",
                        warnings=[str(exc)], **exc.details)
    except OSError:
        code = 6
        output = result(operation, outcome="failed", readiness="blocked", warnings=["IO/permission failure; inspect access to the specified paths"])
    except (KeyError, TypeError, ValueError):
        code = 2
        output = result(operation, outcome="failed", readiness="blocked", warnings=["Invalid structured input"])
    print(json.dumps(clean(output), ensure_ascii=True, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
