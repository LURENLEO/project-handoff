# 示例交接包

`source.zip` 是用仓库 `project-handoff/tests/make_example.py` 从合成计算器项目真实生成的源码自包含包。包内保存的工作是：`add(a, b)` 仍返回 `None`，下一步应按项目规则完成加法并运行测试。示例没有真实凭据或个人聊天记录。

在仓库根目录运行：

```text
python project-handoff/scripts/handoff.py restore --archive examples/relay/source.zip --target <全新空目录> --dry-run
python project-handoff/scripts/handoff.py restore --archive examples/relay/source.zip --target <全新空目录> --apply
```

恢复成功后，结果 JSON 中的 `snapshot_path` 指向新项目里的快照。用该路径继续：

```text
python project-handoff/scripts/handoff.py verify --snapshot <刚才返回的 snapshot_path>
python project-handoff/scripts/handoff.py resume --root <恢复目标目录> --snapshot <刚才返回的 snapshot_path> --read-only
```

若要测试接手者是否保护**交接后**的新改动，可先在恢复目录的 `notes.txt` 末尾加一行，再执行 `resume`。它应报告漂移并保留当前内容。CLI 不会自行完成 `add`；将当前项目、安装好的 Skill 和恢复后的快照交给新的 agent，明确请求“接手并继续”，由其读规则、实施并验证下一步。

这个示例包携带生成时的项目身份与哈希，不认证发布者；请将它作为测试数据使用。
