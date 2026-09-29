# Changelog

## v1.1.0 (2026-09-29)

Protocol 1.1. Package format stays 1.0-compatible.

**Added**

- `quick --root <project> --note "<text>"`: one-command low-friction save; full three-layer Git capture with semantic coverage honestly marked unknown.
- `draft --root <project> [--out context.draft.json]`: generates a context skeleton with mechanical facts pre-filled and semantic domains as explicit TODO placeholders; `save` refuses drafts until every placeholder is replaced (exit code 2 lists unfinished domains).
- `diff --snapshot <entry> --root <project> [--limit N]`: read-only drift details since a snapshot (per-file changes + Git-level changes); writes no receipt, performs no identity corroboration. Same drift computation as `resume`.
- `gc --root <project> [--keep-last N] [--older-than DAYS] [--prune-staging] --dry-run|--apply`: prunes orphaned snapshots and stale staging transactions under a writer lock. The CURRENT ancestor chain and receipts are never removed.
- `report --snapshot <entry> [--out HANDOFF.md] [--stdout]`: deterministic human-readable handoff document rendered from `state.json` (work items, next-step checklist, how to resume). `--stdout` is a documented human-readable exception like `--help`.
- `doctor [--root <project>]`: environment self-check — Python/Git versions, skill installation paths across hosts, detected clients, and store health (CURRENT verification, stale locks, staging leftovers) with remediation hints.
- Three-tier secret filtering: literal credential shapes are excluded (unchanged); assignment-shaped matches (`api_key = config[...]`) are now kept but flagged as `secret_suspicious` review gaps instead of blocking restore; `.handoff/redact.json` supports `allow_globs` (flagged `secret_allowlisted`) and `strict`.
- Exit code 1 for unexpected internal errors; stdout still emits exactly one JSON document (protocol contract preserved on any failure path).
- `readiness` gains `not_applicable` for helper commands that declare no continuation (draft/diff/gc/report/doctor).
- Deterministic release packaging (`tests/package_skill.py`) and a tag-triggered release workflow with SHA256SUMS.

**Fixed**

- Unexpected exceptions no longer break the single-JSON stdout contract.
- `store.save` validated and re-validated the context redundantly; validation now runs once with continuity checked separately.
- `portability.baseline_check` rebuilt the baseline OID set per object (quadratic); now built once.
- Writer-lock release no longer masks the operation result when the lock file is removed externally.
- `core.hooksPath=/dev/null` is only set on POSIX (it is not a valid Windows path; hooks were never invoked anyway).
- Manifest `tool_version` now tracks the tool release (1.1.0) separately from the package `schema_version` (1.0.0).

## v1.0.0 (2026-09-27)

Initial release.

- `save` / `verify` / `inspect` / `resume` / `export` / `restore` CLI with single-JSON stdout contract and documented exit codes.
- Three-layer Git state capture (HEAD, index, working tree, untracked files) with raw-byte payloads, SHA-256 deduplication, and Git-OID re-verification.
- Immutable snapshots, atomic `CURRENT.json` publication, crash-safe staging with fault-injection test coverage.
- Resume identity corroboration, receipts, drift reporting, and validation freshness.
- ZIP export/restore with path-traversal, collision, and zip-bomb protections; restore only into empty directories.
- 22 integration tests on Windows and Ubuntu CI.
