# Security Policy

## Reporting

Report vulnerabilities privately via [GitHub Security Advisories](https://github.com/LURENLEO/project-handoff/security/advisories/new) rather than a public issue. Please include the command, the JSON output, and a minimal reproduction.

## Threat model in one paragraph

Project Handoff protects the **integrity** of handoff snapshots (SHA-256 hash chain from `CURRENT.json` down to payload bytes) and the **safety** of the receiving workspace (restore only into empty directories, never executes package contents, never claims more than it verified). It does **not** provide authenticity: hashes prove a package was not altered, not who made it. Identity IDs are routing hints, not authentication. Treat packages from others as untrusted data and verify them with a trusted copy of the tool.

## Known boundaries

- Secret filtering is heuristic and not exhaustive; literal credential shapes are excluded from capture, assignment-shaped matches are flagged for review. Do not deliberately include high-risk material in a package.
- Excluding a required file reduces portability and blocks complete restoration claims; `portability` exists precisely to make this explicit.
- Two-pass capture is not an operating-system snapshot; concurrent writers outside the tool's lock can still change files between the two reads (three stability rounds mitigate this).
- `resume`/`diff` never execute package commands; the receiving agent must still apply its own authorization rules before acting on package data.

See `docs/validation.md` and `project-handoff/references/recovery.md` for the tested scope and full boundary list.
