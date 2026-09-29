# 保存交接

先定位实际项目根、当前工作线与 store。Git 需用工作区根，多个仓库分别保存并在 project/collaboration 互相登记。
先读当前适用规则；`inspect` 只读扫描当前状态，返回代码指纹、明确工作线的历史和未发布事务。

摩擦选择：作业中途的轻量保存用 `quick --note "<一句话>"`，语义域如实 unknown；正式交接用 `draft --out <draft.json>` 生成骨架（机械事实已预填，语义域是 TODO 占位），补齐后 `save --context <draft.json>`。含 `draft_template` 来源或 TODO statement 的 context 会被 save 以码 2 拒绝并列出未完成域。quick 之后再做正式 save 时，语义 ID 从上一个 state.json 恢复维护。

```text
python <skill>/scripts/handoff.py inspect --root <project> --stream <stream>
python <skill>/scripts/handoff.py save --root <project> --context <context.json> --stream <stream>
```

默认 stream 为 `default`。已有多条工作线且无法确定本次归属时才澄清，不按时间猜最新包。自定义存储需每次传 `--store`。

从当前可见对话产出 [context schema](../assets/context.schema.json) 所定义的 JSON，参考 [示例](../assets/context.example.json) 的字段形状。
在持久化输入 JSON 前先移除凭据和高风险内容。脚本只保证自己写出的草稿经过过滤，不能追溯清除调用方已写下的原始秘密。
建议将输入放在 store 外的允许临时位置，避免语义文件改变项目指纹。

每个域有 coverage 与原因。`complete` 的空数组表示已确认没有，不可访问应为 `unknown`。
语义审阅对应的 `inspect.code_fingerprint` 写入 `observed_fingerprint`。无法核对则用 null，结果将有条件。
当前 context 是完整语义状态，不是增量：从上一个 `state.json` 继续维护稳定任务/约束/决策/缺口 ID，加入新事实和 `superseded_by`、`resolved`，不要删除旧 ID。
最新失败、未做验证、半成品函数、下一处修改与失败分支都要保留。过去 passed 的证据保留结果；脚本另算 freshness。

事实来源可以是可见用户请求短摘录加本地定位，不编造消息 ID。只写简明理由、可见观察，不写内部推理。
规则、依赖锁文件、环境安装方式、多个仓库、外部动作检查方法应明确登记。文件型附件需放在范围内或显式纳入；只有 URL、不可获取附件或外部系统状态写入 gaps。

`--include-ignored <相对文件>` 可重复使用，仅纳入明确选中的 ignored 文件；不传目录，不扫描 home。
默认每文件 64 MiB、载荷合计 512 MiB；`--max-file <字节>` 可调低上限。超大 tracked 文件也会明确排除并阻止完整恢复声明。
默认排除凭据文件、缓存/构建/依赖目录和 store 自身；已跟踪普通源码即使在构建目录也采集。默认未跟踪 ignored 文件不属于声明源码范围。
secret 过滤：字面凭据形状排除字节；键名形状赋值记 `secret_suspicious` 并保留字节待审。误报可用 `<store>/redact.json` 配置：`{"allow_globs": ["tests/fixtures/*"], "strict": false}`。

保存不修改 `.gitignore` 或 AGENTS.md；可建议用户忽略 `.handoff/`。发布链为 staging → 校验 → snapshot 重命名 → CURRENT 原子替换。
CURRENT 更新前失败旧包仍有效；更新后发生故障时新 CURRENT 仍需核验，不根据命令失败就认定新快照不存在。
写锁仅协调本工具；不自动按超时删除锁。失败草稿/孤立包处理见 recovery。

返回后检查三类结果、排除影响与语义指纹。若准备删除原工作区，先 export source，并在隔离空目录完成 restore 验证。
