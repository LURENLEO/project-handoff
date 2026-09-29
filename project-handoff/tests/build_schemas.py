"""Regenerate protocol documentation and the usable context template."""
import json
from pathlib import Path
from fixtures import context
from handoff_core.context import DOMAINS

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def generate():
    ASSETS.mkdir(exist_ok=True)
    fact = {"type": "object", "required": ["id", "statement", "source", "observed_at", "confidence"], "properties": {
        "id": {"type": "string", "minLength": 1}, "statement": {"type": "string", "minLength": 1},
        "source": {"type": "object", "required": ["kind", "ref"], "properties": {
            "kind": {"enum": ["user_message", "file", "tool_result", "external_reference", "agent_assessment", "draft_template"]}, "ref": {"type": "string", "minLength": 1}}},
        "observed_at": {"type": "string", "minLength": 1}, "confidence": {"enum": ["high", "medium", "low", "unknown"]},
        "evidence_ids": {"type": "array", "items": {"type": "string"}}, "superseded_by": {"type": ["string", "null"]}}}
    coverage = {"type": "object", "required": DOMAINS, "properties": {d: {"type": "object", "required": ["status", "reason"], "properties": {
        "status": {"enum": ["complete", "partial", "unknown", "not_applicable"]}, "reason": {"type": "string", "minLength": 1}}} for d in DOMAINS}}
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "https://project-handoff.local/context.schema.json",
              "title": "Project Handoff semantic context 1.x", "type": "object", "required": ["schema_version", "coverage", *DOMAINS],
              "$defs": {"fact": fact}, "properties": {"schema_version": {"type": "string", "pattern": "^1\\.[0-9]+\\.[0-9]+$"},
                 "observed_fingerprint": {"type": ["string", "null"]}, "coverage": coverage}}
    for d in DOMAINS:
        schema["properties"][d] = {"type": "array", "items": {"$ref": "#/$defs/fact"}}
    schema["properties"]["intent"] = {"allOf": [{"$ref": "#/$defs/fact"}, {"type": "object", "required": ["original_goal", "current_goal", "acceptance", "scope", "non_goals", "corrections"], "properties": {
        **{k: {"type": "string", "minLength": 1} for k in ("original_goal", "current_goal")},
        **{k: {"type": "array"} for k in ("acceptance", "scope", "non_goals", "corrections")}}}]}
    extensions = {
        "work_items": {"status": {"enum": ["pending", "in_progress", "blocked", "implemented_unverified", "verified", "cancelled"]}, **{k: {"type": "array"} for k in ("acceptance", "done", "remaining", "files", "depends_on")}},
        "next_actions": {"task_id": {"type": "string"}, **{k: {"type": "array"} for k in ("preconditions", "files")}, **{k: {"type": "string", "minLength": 1} for k in ("action", "expected_result", "validation", "on_failure")}},
        "gaps": {k: {"type": "string", "minLength": 1} for k in ("reason", "impact", "resolution")},
        "validation": {"result": {"enum": ["passed", "failed", "not_run", "interrupted", "unknown"]}, "freshness": {"enum": ["current", "stale", "unknown"]},
            **{k: {} for k in ("started_at", "ended_at", "exit_code", "log", "code_fingerprint", "environment")},
            "command": {"type": "object", "required": ["argv", "cwd_ref", "env_names", "purpose", "side_effects"], "properties": {
                "argv": {"type": "array", "items": {"type": "string"}}, "env_names": {"type": "array"}, **{k: {"type": "string"} for k in ("cwd_ref", "purpose", "side_effects")}}}}
    }
    for d, props in extensions.items():
        schema["properties"][d]["items"] = {"allOf": [{"$ref": "#/$defs/fact"}, {"type": "object", "required": list(props), "properties": props}]}
    write("context.schema.json", schema)
    state = json.loads(json.dumps(schema))
    state["$id"] = "https://project-handoff.local/state.schema.json"
    state["required"] += ["snapshot_id", "parent_snapshot_id", "identity"]
    identity = {"type": "object", "required": ["project_id", "workspace_id", "stream_id"], "properties": {k: {"type": "string", "minLength": 1} for k in ("project_id", "workspace_id", "stream_id")}}
    state["properties"].update(snapshot_id={"type": "string"}, parent_snapshot_id={"type": ["string", "null"]}, identity=identity)
    write("state.schema.json", state)
    props = dict(schema_version=schema["properties"]["schema_version"], tool_version={"type": "string"}, snapshot_id={"type": "string"}, parent_snapshot_id={"type": ["string", "null"]}, identity=identity,
                 captured_started_at={"type": "string"}, captured_ended_at={"type": "string"}, code_fingerprint={"type": "string", "pattern": "^[0-9a-f]{64}$"},
                 stability={"enum": ["double_checked"]}, readiness={"enum": ["ready", "conditional", "blocked"]}, portability={"enum": ["local_only", "portable_with_prerequisites", "self_contained"]},
                 exclusions={"type": "array"}, gaps={"type": "array"}, required_capabilities={"type": "array"},
                 files={"type": "object", "additionalProperties": {"type": "object", "required": ["size", "sha256", "purpose", "type", "mode", "encoding", "original"], "properties": {
                     "size": {"type": "integer", "minimum": 0}, "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}, "purpose": {"type": "string"}, "type": {"const": "file"}, "mode": {"const": "0644"}, "encoding": {"enum": ["utf-8", "binary"]}, "original": {"type": "boolean"}}}})
    write("manifest.schema.json", {"$schema": schema["$schema"], "type": "object", "required": list(props), "properties": props})
    write("context.example.json", context())


def write(name, value):
    (ASSETS / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    generate()
