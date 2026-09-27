# Project Handoff

[![Tests](https://github.com/LURENLEO/project-handoff/actions/workflows/tests.yml/badge.svg)](https://github.com/LURENLEO/project-handoff/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

[English](README.md) · 简体中文

Project Handoff 是一个离线 Codex Skill，用于保存项目开发交接包，并帮助下一位 agent 在核对当前项目状态后继续工作。它把语义状态与磁盘事实分开记录：任务、约束、决策、未知项由 agent 整理；Git HEAD、暂存区、工作树和未跟踪文件由 Python 工具采集。默认在项目内保存不可变快照，不需要模型 API、数据库或常驻服务。

> 本项目基于 [MIT 许可证](LICENSE) 开源，可在署名的前提下自由使用、修改和再分发。

## 功能

- `save`：保存语义状态和原始文件字节，分别保全 HEAD、index、工作树与未跟踪文件；原子更新 `CURRENT.json`。
- `verify`：校验协议、引用、文件哈希和载荷完整性。
- `inspect`：查看指定项目和工作线的当前快照、历史、孤立包和实际代码指纹。
- `resume`：核对项目身份与交接后的改动，生成接手结果和 receipt；后续开发由 agent 在当前授权下执行。
- `export` / `restore`：生成本地 ZIP 包，在空目录规划或执行恢复。`source` 模式保留声明范围的源码，`baseline` 模式额外核对指定本地 Git 基线。

每次结果分别报告 `integrity`（包完整性）、`readiness`（当前接续条件）和 `portability`（携带能力）。缺失的上下文、排除的文件和不支持的 Git 状态会明确列出，不把有交接说明等同于可恢复。

## 要求与安装

- Python 3.11 或更新版本。核心运行仅使用 Python 标准库。
- Git 项目需要系统 Git；无 Git 的普通目录也支持保存与源码恢复。
- [Codex](https://learn.chatgpt.com/docs/build-skills) 可使用仓库中的 `project-handoff/SKILL.md`；CLI 也能单独运行。

克隆或下载仓库后，将整个 `project-handoff` 文件夹复制到个人技能目录 `~/.agents/skills/project-handoff`，或放到项目的 `.agents/skills/project-handoff`。Windows 对应路径通常是 `%USERPROFILE%\.agents\skills\project-handoff`。Codex 使用时输入 `$project-handoff 保存交接` 或 `$project-handoff 接手并继续`。不要同时在个人级和项目级安装同名副本。

安装后可先运行：

```text
python project-handoff/scripts/handoff.py --help
```

文档中的 `project-handoff/scripts/handoff.py` 路径以本仓库根目录为基准；从别的目录运行时，请换成 Skill 的实际绝对路径。CLI 通过 stdout 输出单个 JSON 对象，适合自动化读取。

## 快速开始

`save` 需要一个结构化的 `context.json`。从 [示例](project-handoff/assets/context.example.json)复制字段形状并替换为**当前项目的真实事实和来源**；不要把示例中的任务、授权或验证结果原样当作自己项目的事实。完整字段及覆盖范围见 [保存指南](project-handoff/references/save.md)和 [协议](project-handoff/references/protocol.md)。对话中的未知或不可访问内容应在 `coverage` 和 `gaps` 中注明。

```text
python project-handoff/scripts/handoff.py inspect --root <项目根目录>
python project-handoff/scripts/handoff.py save --root <项目根目录> --context <context.json>
python project-handoff/scripts/handoff.py verify --snapshot <CURRENT.json 或快照目录>
python project-handoff/scripts/handoff.py resume --root <项目根目录> --snapshot <CURRENT.json 或快照目录>
```

保存时，先用 `inspect` 取得代码指纹并核对语义，再把它写入 `observed_fingerprint`。`save` 返回快照与 `CURRENT.json` 路径；交给接手者的是明确路径和当前项目。若用户要求继续，接手 agent 在核验并阅读当前适用的 `AGENTS.md` 后，执行仍有效且已授权的 `next_actions`。CLI 自身只负责检查，不运行项目命令。

跨目录恢复先规划，再在**空目录**执行：

```text
python project-handoff/scripts/handoff.py export --snapshot <快照目录> --mode source --output <新包.zip>
python project-handoff/scripts/handoff.py restore --archive <包.zip> --target <空目录> --dry-run
python project-handoff/scripts/handoff.py restore --archive <包.zip> --target <空目录> --apply
```

`baseline` 导出需要目标另有精确 Git 基线，恢复时加 `--baseline <本地仓库>`；不会自动 fetch。原仓库有新的用户改动时，请用 `resume` 查看差异，不把旧包恢复覆盖到原仓库。更多边界见 [恢复指南](project-handoff/references/recovery.md)。

## 可运行示例

[示例源码包](examples/relay/source.zip)由工具真实生成，供隔离目录中试用 `verify`、`restore` 和 `resume`。操作步骤见 [示例说明](examples/relay/README.md)。该包仅含合成的计算器项目和交接事实，不包含用户项目资料。

也可以用 `python project-handoff/tests/make_example.py --output <全新目录>` 创建自己的隔离接力示例。生成的提示词包含**本机绝对路径**，用于本机测试；上传仓库前应检查生成材料。独立新对话接力仍需人工或 agent 按提示执行，脚本不会创建新对话。

## 开发与验证

```text
python project-handoff/tests/run_checks.py --report test-results.json
```

测试使用临时 fixture 仓库，覆盖 Git 三层状态、无 Git 与无 HEAD、故障注入、并发锁、路径与压缩限制、敏感信息排除、跨平台恢复等。可选安装 `jsonschema` 运行 schema 一致性附加测试；核心运行不需要它。GitHub Actions 在 Windows 和 Ubuntu 上运行同一套测试。历史开发验收范围与已知限制见 [验收记录](docs/validation.md)。

## 数据与边界

交接包可能包含未公开源码，请先检查内容再分享。默认排除常见凭据文件，文本过滤是启发式，不能保证发现全部秘密。被排除的必要文件会降低携带能力，完整恢复将被阻断。默认存储在项目 `.handoff/`；工具不会自行修改 `.gitignore`，可按项目习惯手动忽略此目录。

`source` 模式保留声明范围的源码和原 HEAD 作为浅历史边界，不包含完整 Git 历史或外部服务。冲突中的 Git 操作、未递归采集的子模块、只有指针的 LFS 文件、特殊 index flags 和 Windows 符号链接等会明确标记为不支持自动完整恢复。双次采集检查也不是操作系统快照，交接后发生的新改动应由接手者重新判断。详细说明见 [Skill 文档](project-handoff/SKILL.md)与 [已知限制](project-handoff/references/recovery.md)。

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。
