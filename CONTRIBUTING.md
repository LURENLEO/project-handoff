# Contributing

Thanks for your interest in improving Project Handoff.

## Ground rules

- Core runtime is Python 3.11+ **standard library only** — no third-party runtime dependencies. `jsonschema` is an optional development dependency for one schema test.
- The CLI contract is strict: stdout carries exactly one JSON document, never project commands. Any new command must keep this contract, including on failure paths.
- Package format changes must keep 1.x compatibility: additive optional fields only; bump the protocol document and this repository's CHANGELOG together.
- Safety invariants are non-negotiable: snapshots are immutable, restore targets must be empty, package contents are never executed, and `readiness`/`integrity`/`portability` are reported honestly.

## Workflow

1. Fork, then create a branch.
2. Add or extend integration tests in `project-handoff/tests/test_handoff.py` (fixture repos are created per-test in temporary directories; fault injection uses `HANDOFF_TEST_FAULT` / `HANDOFF_TEST_CRASH`).
3. Run the full suite:
   ```text
   python project-handoff/tests/run_checks.py --report test-results.json
   ```
4. If you changed the schema definition, regenerate the assets instead of editing them by hand:
   ```text
   python project-handoff/tests/build_schemas.py
   ```
5. Update `README.md` and `README_zh.md` together (both languages), plus the relevant guide under `project-handoff/references/`.
6. Open a pull request describing the behavior change and the tests that pin it.

## Reporting issues

Include the exact command, the JSON output (redact anything sensitive first), platform, Python version, and Git version. `doctor --root <project>` output helps a lot.
