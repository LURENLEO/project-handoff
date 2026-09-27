# 协议 1.0

JSON Schema 为 [context](../assets/context.schema.json)、[state](../assets/state.schema.json)、[manifest](../assets/manifest.schema.json)。运行时用显式类型、引用和语义检查，无 jsonschema 依赖。
顶层 context/state 有 `coverage` 字典，覆盖设计中的全部 18 个信息域。intent 是对象，其余是事实数组。
所有事实带唯一 id、statement、source.kind/ref、observed_at、confidence。可添加文件/符号、原因、替代方案、重开条件等字段；未知可选字段保留。
不宣称 schema 可以证明模型语义完整。verified 任务必须引用 passed 记录；证据时效另行比较，不把过去真实成功改写为失败。

| 维度 | 取值 | 解释 |
|---|---|---|
| integrity | valid / invalid / not_checked | 哈希、版本、引用和文件完整性；不是签名 |
| readiness | ready / conditional / blocked | 已声明下一步的接续条件；agent 仍需判断当前授权与前提 |
| portability | local_only / portable_with_prerequisites / self_contained | 声明源码/材料的携带能力，不含系统环境和外部服务 |

save 完整捕获声明范围，源对象在 payload 按 SHA-256 去重；HEAD commit/tree/blob 与 index blob 另以 Git OID 关联。
工作树记录原始字节/删除/链接，index 记录模式、OID 与 stage；恢复不依赖补丁，也不调用 textconv、外部 diff 或网络 fetch。
Git 原始 index 文件只记录哈希供捕获一致性检查，恢复重建逻辑条目，保留 HEAD/index/worktree 语义而不承诺 index 缓存字节相同。

manifest 不自哈希；CURRENT 存 manifest SHA-256；manifest.files 存其他文件哈希与大小；独立 ZIP 的 EXPORT.json 存 manifest SHA-256。
主版本不支持返回 7；未知必需能力拒绝。次版本可选字段保留。迁移生成新包，不修改原包。
路径为逻辑相对路径；禁止绝对路径、..、设备名、大小写碰撞。非 UTF-8 Git 名称保存可逆 base64 排除条目，第一版不能恢复此类文件。

机器 stdout 为单个 JSON：operation/outcome/integrity/readiness/portability/snapshot_path/warnings/gaps/next_steps，再加各模式具体字段。`--help` 是例外的人类说明。

| 退出码 | 含义 |
|---|---|
| 0 | 操作完成；readiness 仍可能 conditional/blocked |
| 2 | 参数或 context schema 不合法 |
| 3 | 包损坏、引用断裂、导入路径/压缩限制失败 |
| 4 | 身份、基线或恢复前提不满足 |
| 5 | 锁冲突或三次捕获均不稳定 |
| 6 | IO/权限/故障注入错误 |
| 7 | 不支持版本或平台能力 |

文件总量/单文件/压缩比限制：20,000 文件、512 MiB、64 MiB、1000:1。达到限制明确失败，不静默截断。
