# Launch & Distribution Kit

This folder collects ready-to-paste launch materials and the distribution checklist. Everything is safe to publish: it contains no project secrets.

## 1. GitHub repository settings (one-time, 2 minutes)

**Topics** (repo → About → gear icon, or `gh repo edit --add-topic`):

```
agent-skills, claude-code, codex, zcode, ai-agents, handoff, session-handoff,
context-management, git, snapshot, developer-tools, python
```

**Description**:

```
Verifiable handoff snapshots for AI coding agents — capture uncommitted work (HEAD + index + worktree) as tamper-evident snapshots and let the next agent verify and resume. MIT, Python 3.11+ stdlib.
```

**Website**: leave empty or point to the README anchor `#quick-start`.

**Releases**: push a tag to trigger the release workflow:
```bash
git tag v1.1.0 && git push origin v1.1.0
```

## 2. Skill directory submissions

| Directory | How |
|---|---|
| [skills.sh](https://skills.sh) | Submit the repo; supports `npx skills` style installation from GitHub repos |
| [skillsdirectory.com](https://skillsdirectory.com) | Submit URL + one-line description |
| [mcpmarket.com](https://mcpmarket.com) | Has a Claude Code skill section; submit repo |
| [llmbase.ai](https://llmbase.ai) | Lists skills installable via `npx skills` |
| Awesome lists | PR to `awesome-claude-code`, `awesome-claude-skills`, `awesome-codex` (paste text below) |

**Awesome-list PR entry (EN):**
```markdown
- [project-handoff](https://github.com/LURENLEO/project-handoff) — Verifiable handoff snapshots for AI coding agents: byte-exact capture of HEAD/index/worktree/untracked files, hash-chained snapshots, drift detection, and one-command `quick` saves. Python 3.11+ stdlib, no LLM needed to verify.
```

**目录站提交文案（中文）：**
> 可验证的项目交接快照工具：逐字节捕获 HEAD/暂存区/工作树/未跟踪文件，哈希链防篡改，接手时自动报告漂移，`quick` 一条命令存档。Python 3.11+ 标准库，核验无需 LLM。

## 3. Launch posts (copy-paste ready)

### Reddit — r/ClaudeAI (title)
**I built a skill that captures uncommitted work as verifiable snapshots — "git push" for handoffs between agents/sessions**

Body:
The problem: you're mid-refactor, the context window fills up or the session dies. `git stash` flattens staged/unstaged and scatters untracked files; a WIP commit pollutes history; handoff markdown is unverifiable prose.

Project Handoff captures Git HEAD + index + working tree + untracked files byte-for-byte into hash-chained immutable snapshots, next to semantic context (tasks/decisions/next-steps) the agent writes. The next session runs `verify` (every byte re-hashed), `diff` (what changed since), then `resume` (identity corroboration + receipt — it never executes historical commands).

- One-command save: `handoff.py quick --root . --note "..."` (semantics honestly marked unknown)
- Full save: `draft` generates a skeleton, agent fills semantics, `save` refuses unfilled drafts
- Cross-machine: `export` → `restore` (only into empty dirs, never overwrites)
- Python 3.11+ stdlib only, MIT, no model API needed. CI on Windows + Ubuntu, 34 integration tests incl. fault injection at every publish step.

Repo: https://github.com/LURENLEO/project-handoff — feedback welcome, especially on the resume identity-corroboration flow.

### Reddit — r/ChatGPTCoding / r/codex (title)
**Codex/Claude skill: verifiable handoff snapshots for uncommitted work (MIT, stdlib-only CLI)**

Body: same as above, first paragraph shortened.

### V2EX（标题）
**project-handoff：给 AI 编程 agent 的可验证交接快照（未提交工作的 git push）**

正文要点：
- 场景：上下文满了 / 会话断了 / 换 agent（Codex ↔ Claude Code ↔ ZCode），工作还没到能 commit 的程度
- 方案：HEAD + 暂存区 + 工作树 + 未跟踪文件逐字节进哈希链快照；语义（任务/决策/下一步）由 agent 单独记录；接手方先 verify 每个 byte 再 resume
- quick 一条命令存档；draft 生成骨架补语义；diff 只读看漂移；report 生成人可读交接文档可贴 PR
- 跨机器 export/restore，只恢复到空目录绝不覆盖
- 纯 Python 3.11+ 标准库，MIT，核验不需要 LLM；Windows/Ubuntu CI，34 个集成测试
- 链接：https://github.com/LURENLEO/project-handoff

### 即刻 / 朋友圈（短文案）
做了个开源小工具 project-handoff：AI 编程 agent 换会话/换机器时，把未提交的工作（HEAD+暂存区+工作树）逐字节存成防篡改快照，下个 agent 先核验每个字节再接着干。quick 一条命令存档，纯 Python 标准库。GitHub 搜 LURENLEO/project-handoff，求 star 求反馈 🙏

### X / Twitter thread (first tweet)
Uncommitted work shouldn't die when your AI coding session ends.

project-handoff captures HEAD + index + worktree byte-for-byte into hash-chained snapshots the next agent can *verify* before resuming.

quick one-command save · draft→save for full semantics · export/restore across machines

MIT, stdlib-only: https://github.com/LURENLEO/project-handoff

## 4. Post-launch checklist

- [ ] Push tag v1.1.0 → release workflow publishes ZIP + SHA256SUMS
- [ ] Set topics + description (section 1)
- [ ] Submit to the 4 directories above
- [ ] Post Reddit (EN), V2EX (CN), 即刻 (CN), X (EN) — space them over 1–2 days
- [ ] Watch first issues; answer within 24h during launch week
- [ ] After first external star: add the repo to your GitHub profile README
