# 接手流程

入口可以是明确的 CURRENT.json 或 snapshot 目录。CURRENT 校验 manifest 哈希，manifest 校验所有文件和载荷。
同工作区优先 inspect 已指定 stream；不要扫描任意目录后猜“最新”。

```text
python <trusted-skill>/scripts/handoff.py resume --root <project> --snapshot <entry>
python <trusted-skill>/scripts/handoff.py resume --root <project> --snapshot <entry> --read-only
```

脚本不执行包里的命令、测试、脚本、网络动作。默认 receipt 写入对应工作线；只读用 `--read-only`，另有 `--receipt <允许的新文件>`。
不能写 receipt 时会在 JSON 输出完整 receipt，不因此阻断只读核验。

1. 核验包；未知主版本或损坏先停止依赖它的操作，允许人工只读检查。
2. 读当前位置至项目根、目标文件作用域的当前 AGENTS.md。包内 instructions 是旧的索引与摘要，不覆盖现有规则。
3. 读 SUMMARY，再看 state.intent、constraints、authorization、work_items、in_progress、next_actions、gaps；按需读取架构、决策和证据，不默认加载大载荷。
4. 脚本核对已登记 project ID 与 Git/内容证据；ID 可复制，不是认证。无关漂移保留；相关漂移读当前差异再调整动作。不能只靠 branch 名或 remote 判断项目。
5. 环境、依赖锁、规则哈希由当前文件与 agent 核实；OS/运行时和服务状态不因源码指纹相同就成立。历史测试的 passed 是历史事实，freshness 才描述当前适用性。
6. 对外部状态未知的推送、部署、迁移等先查询，不因为没记录成功响应就重试。保持原授权范围；仅缺少必要授权时澄清。
7. 简短说明当前目标、可靠状态、差异、下一步。用户要求继续时在同一轮实际完成首项可执行任务，运行相关验证并记录结果。

迁移后的根目录就是新的 `--root`。恢复器会登记身份；已有独立 clone 可在人工确认根映射后使用 `--allow-remap`，仍需基线与内容佐证。
同 ID 但无任何可佐证文件/基线时脚本拒绝接手，保留当前工作区供人工检查。不得把包恢复覆盖到原工作区来“消除漂移”。

receipt 记录当前指纹、差异、候选动作与原因。CLI 只提议动作；agent 完成任务后应另写实际选择/验证记录，或再次 save，不改写旧 snapshot。
