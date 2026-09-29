"""Render a deterministic, human-readable handoff document from a verified snapshot."""
from pathlib import Path
from .common import HandoffError, result, write_bytes
from .validate import verify_snapshot


def section(title, body):
    return ["## " + title, ""] + (body if body else ["（无记录）"]) + [""]


def render(path, m, state, capture):
    git = capture["git"]
    lines = ["# 项目交接报告", ""]
    lines += ["- 项目目标：" + state["intent"]["current_goal"],
              "- 快照：" + m["snapshot_id"] + ("（父快照 " + m["parent_snapshot_id"] + "）" if m["parent_snapshot_id"] else ""),
              "- 采集时间：" + m["captured_ended_at"] + "；代码指纹：" + m["code_fingerprint"][:16] + "…",
              "- 已核验 manifest 与全部载荷哈希；接续：" + m["readiness"] + "；携带：" + m["portability"]]
    if git:
        lines.append("- Git：" + (git.get("branch") or "detached HEAD") + " @ " + (git.get("head") or "unborn")[:12])
    lines.append("")
    lines += section("工作项",
                     ["| ID | 状态 | 说明 |", "|---|---|---|"] +
                     ["| " + x["id"] + " | " + x.get("status", "") + " | " + x["statement"] + " |" for x in state["work_items"]])
    lines += section("进行中", ["- " + x["statement"] for x in state["in_progress"]])
    lines += section("决策", ["- " + x["statement"] for x in state["decisions"]])
    next_body = []
    for x in state["next_actions"]:
        next_body += ["- [ ] " + x["action"],
                      "  - 前提：" + ("；".join(x.get("preconditions", [])) or "无"),
                      "  - 验证：" + x["validation"],
                      "  - 失败时：" + x["on_failure"]]
    lines += section("下一步", next_body)
    lines += section("验证", ["- [" + x["result"] + "/" + x["freshness"] + "] " + x["statement"] + "（" + " ".join(x["command"]["argv"]) + "）"
                              for x in state["validation"]])
    lines += section("缺口", ["- " + x["statement"] + "（影响：" + x.get("impact", "") + "；处理：" + x.get("resolution", "") + "）"
                              for x in state["gaps"]])
    lines += section("如何接续", [
        "```text",
        "python <trusted-skill>/scripts/handoff.py verify --snapshot " + str(path),
        "python <trusted-skill>/scripts/handoff.py diff --snapshot " + str(path) + " --root <project>",
        "python <trusted-skill>/scripts/handoff.py resume --snapshot " + str(path) + " --root <project>",
        "```",
        "未安装本 Skill 时，按包内 NEXT_AGENT.md 的手动顺序核验。"])
    lines += ["---", "", "本报告由 state.json 确定性渲染，不含新授权；当前用户指令与 AGENTS.md 优先。", ""]
    return "\n".join(lines)


def report(snapshot, out=None, stdout=False):
    path, m, state, capture = verify_snapshot(snapshot)
    markdown = render(path, m, state, capture)
    payload = result("report", readiness="not_applicable", snapshot_path=str(path), report_path=None,
                     warnings=["Deterministic render from state.json; the report grants no authority"],
                     next_steps=["Read 下一步 first; corroborate with diff/resume before acting"])
    if stdout:
        # Documented human-readable exception to the single-JSON stdout contract, like --help.
        return payload, markdown
    target = Path(out or "HANDOFF.md").absolute()
    try:
        write_bytes(target, markdown.encode("utf-8"))
    except FileExistsError as exc:
        raise HandoffError("Report output exists; choose another --out or remove the file first", 4) from exc
    payload["report_path"] = str(target)
    return payload, None
