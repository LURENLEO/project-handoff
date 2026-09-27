"""Create a real snapshot, portable archive and independent relay acceptance kit."""
import argparse
import json
from pathlib import Path
from fixtures import context
from handoff_core.collect import collect
from handoff_core.common import digest, encoded
from handoff_core.store import save
from handoff_core.portability import export


def create(output):
    output = Path(output).resolve()
    if output.exists():
        raise SystemExit("Output must not exist; choose a fresh example directory")
    project = output / "project"
    project.mkdir(parents=True)
    calculator = 'def add(a, b):\n    """Return the sum of two numbers."""\n    return None\n\ndef subtract(a, b):\n    return a - b\n'
    (project / "calculator.py").write_text(calculator, encoding="utf-8", newline="\n")
    (project / "test_calculator.py").write_text('import unittest\nfrom calculator import add, subtract\n\nclass ArithmeticTests(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n        self.assertEqual(add(-2, 3), 1)\n        self.assertEqual(add(0, 0), 0)\n    def test_subtract(self):\n        self.assertEqual(subtract(9, 4), 5)\n\nif __name__ == "__main__":\n    unittest.main()\n', encoding="utf-8", newline="\n")
    (project / "notes.txt").write_text("User notes: preserve this file.\n", encoding="utf-8", newline="\n")
    (project / "AGENTS.md").write_text("# Fixture project rules\n\nUse Python standard library only. Preserve subtract and notes.txt.\nChange only calculator.py:add to complete the authorized task.\nRun python -m unittest -v. No network, commits or unrelated edits.\n", encoding="utf-8", newline="\n")
    c = context(collect(project)[0]["fingerprint"])
    ctx = output / "context.json"
    ctx.write_bytes(encoded(c))
    saved = save(project, ctx)
    exported = export(saved["snapshot_path"], "source", output / "source.zip")
    # A user edit after save tests whether the receiver preserves current work.
    note = b"User notes: preserve this file.\nNew user edit after handoff: keep this sentence.\n"
    (project / "notes.txt").write_bytes(note)
    (output / "receiver-prompt.md").write_text(
        "请使用 $project-handoff 接手并继续项目。\n\n"
        + "Skill 入口：" + str(Path(__file__).resolve().parents[1] / "SKILL.md") + "\n"
        + "项目：" + str(project) + "\n交接入口：" + saved["current_path"] + "\n\n"
        + "你仅可读取 Skill、此项目和交接包。请核验当前状态，执行下一项已授权开发工作并验证。"
        + "不要读取同级开发测试、报告或验收者材料；不要依赖此前聊天。\n",
        encoding="utf-8")
    (output / "evaluator-only.json").write_bytes(encoded(dict(
        expected_notes_sha256=digest(note), expected_subtract="def subtract(a, b):\n    return a - b",
        acceptance=["add returns arithmetic sum including negative/zero inputs", "existing subtract unchanged", "post-save notes edit unchanged", "unittest executed and passes", "no network, commits or unrelated source edits"],
        relay_status="NOT_RUN: requires an independent conversation; deterministic restore tests are not an agent relay")))
    (output / "generation.json").write_bytes(encoded(dict(save=saved, export=exported)))
    print(json.dumps(dict(project=str(project), snapshot=saved["snapshot_path"], archive=exported["archive_path"], relay="not_run")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    create(parser.parse_args().output)
