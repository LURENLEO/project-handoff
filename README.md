# Project Handoff

[![Tests](https://github.com/LURENLEO/project-handoff/actions/workflows/tests.yml/badge.svg)](https://github.com/LURENLEO/project-handoff/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

English · [简体中文](README_zh.md)

Project Handoff is an offline Codex skill for saving development handoffs and helping the next agent continue after checking the current project state. It keeps semantic context separate from filesystem facts: the agent records tasks, constraints, decisions, and unknowns; the Python CLI captures Git HEAD, the index, the working tree, and untracked files. By default, it stores immutable snapshots inside the project. It needs no model API, database, or background service.

> Licensed under the [MIT License](LICENSE): you are free to use, modify, and redistribute it with attribution.

## What it does

- `save` records semantic context and original file bytes, preserving HEAD, index, working-tree, and untracked-file states separately. It updates `CURRENT.json` atomically.
- `verify` checks the protocol, references, file hashes, and payload integrity.
- `inspect` shows the current snapshot, history, orphaned snapshots, and actual code fingerprint for a specified project and work stream.
- `resume` checks project identity and changes since the handoff, then produces a handoff result and receipt. The agent performs subsequent development under the user's current authorization.
- `export` and `restore` create a local ZIP archive and plan or perform recovery into an empty directory. `source` mode carries the declared source scope; `baseline` mode also verifies a specified local Git baseline.

Results report `integrity` (package integrity), `readiness` (conditions for resuming now), and `portability` (what the package can carry) separately. Missing context, excluded files, and unsupported Git states are reported explicitly. A handoff description alone does not imply that the project can be restored.

## Requirements and installation

- Python 3.11 or newer. Core runtime uses only the Python standard library.
- System Git for Git projects. Plain directories without Git can also be saved and restored in `source` mode.
- [Codex](https://learn.chatgpt.com/docs/build-skills) can use `project-handoff/SKILL.md`; the CLI also runs independently.

After cloning or downloading this repository, copy the entire `project-handoff` folder to `~/.agents/skills/project-handoff`, or to `.agents/skills/project-handoff` inside a project. On Windows, the personal path is usually `%USERPROFILE%\.agents\skills\project-handoff`. In Codex, invoke `$project-handoff` and ask it to save a handoff or resume work. Avoid installing two copies with the same skill name at personal and project scope.

Check the CLI after installation:

```text
python project-handoff/scripts/handoff.py --help
```

The paths in these commands are relative to the repository root. When running from another directory, use the actual absolute path to the installed skill. The CLI writes one JSON object to stdout for automation.

## Quick start

`save` requires a structured `context.json`. Use the [example](project-handoff/assets/context.example.json) for its field shapes, then replace its contents with **real facts and sources from your project**. Do not treat the example's tasks, authorization, or validation results as facts about your own project. See the [save guide](project-handoff/references/save.md) and [protocol](project-handoff/references/protocol.md) for the full fields and coverage rules. Mark inaccessible or unknown context in `coverage` and `gaps`.

```text
python project-handoff/scripts/handoff.py inspect --root <project-root>
python project-handoff/scripts/handoff.py save --root <project-root> --context <context.json>
python project-handoff/scripts/handoff.py verify --snapshot <CURRENT.json-or-snapshot-directory>
python project-handoff/scripts/handoff.py resume --root <project-root> --snapshot <CURRENT.json-or-snapshot-directory>
```

Before saving, use `inspect` to obtain the code fingerprint, reconcile the semantic context with the current code, and put that fingerprint in `observed_fingerprint`. `save` returns the snapshot and `CURRENT.json` paths; give the next agent an explicit path and the current project. When asked to continue, the receiving agent verifies the package, reads the currently applicable `AGENTS.md`, and performs the first still-valid, authorized `next_actions` item. The CLI only checks and reports; it does not run project commands.

For recovery into another directory, plan first and then apply to an **empty directory**:

```text
python project-handoff/scripts/handoff.py export --snapshot <snapshot-directory> --mode source --output <new-archive.zip>
python project-handoff/scripts/handoff.py restore --archive <archive.zip> --target <empty-directory> --dry-run
python project-handoff/scripts/handoff.py restore --archive <archive.zip> --target <empty-directory> --apply
```

A `baseline` export also requires an exact local Git baseline; pass `--baseline <local-repository>` when restoring. The tool does not fetch objects automatically. If the original project has new user changes, use `resume` to inspect the differences rather than restoring an older package over that project. See the [recovery guide](project-handoff/references/recovery.md) for more boundaries.

## Working example

The [example source archive](examples/relay/source.zip) was generated by the tool from a synthetic calculator project. You can use it to try `verify`, `restore`, and `resume` in an isolated directory. Follow the [example instructions](examples/relay/README.md). It contains no real user project data.

You can also create a fresh, isolated relay fixture with `python project-handoff/tests/make_example.py --output <new-directory>`. Its generated prompt contains **absolute paths on your machine** and is intended for local testing; review generated artifacts before publishing them. A separate new conversation must carry out an independent agent relay test. The script does not create one.

## Development and validation

```text
python project-handoff/tests/run_checks.py --report test-results.json
```

Tests use temporary fixture repositories. They cover Git's three states, plain directories and repositories without HEAD, injected failures, concurrent locks, path and compression limits, sensitive-data exclusions, and cross-platform restoration. Installing `jsonschema` is optional and enables an additional schema-consistency test; core runtime does not require it. GitHub Actions is configured to run the suite on Windows and Ubuntu. See the [validation record](docs/validation.md) for the historical test scope and known gaps.

## Data and limitations

A handoff package may contain unpublished source code. Review it before sharing. Common credential files are excluded by default, but text filtering is heuristic and cannot detect every secret. Excluding a required file reduces portability and blocks a claim of complete restoration. The default store is the project's `.handoff/` directory; the tool does not modify `.gitignore`, so add an ignore rule yourself if appropriate for the project.

`source` mode carries the declared current source scope and preserves the original HEAD as a shallow history boundary. It does not carry full Git history or external services. An in-progress Git conflict operation, uncaptured submodule, LFS pointer without its real content, special index flags, and Windows symlinks are among the cases reported as unsupported for complete automatic restoration. Two-pass capture is not an operating-system snapshot; the receiving agent must reassess changes made after the handoff. See the [skill entry point](project-handoff/SKILL.md) and [recovery limitations](project-handoff/references/recovery.md) for details.

## License

Distributed under the [MIT License](LICENSE).
