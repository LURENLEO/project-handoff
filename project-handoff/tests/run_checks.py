"""Run meaningful checks and save portable, machine-readable test evidence."""
import argparse
import io
import json
import os
import platform
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    tests = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="test_*.py")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(tests)
    report = dict(observed_at=datetime.now(timezone.utc).isoformat(), platform=platform.platform(),
                  python=sys.version, git=subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip(),
                  tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                  skipped=[dict(test=str(t), reason=r) for t, r in result.skipped],
                  successful=result.wasSuccessful(), log=stream.getvalue())
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(stream.getvalue())
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
