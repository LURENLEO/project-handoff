# 导出、恢复与事务修复

```text
python <skill>/scripts/handoff.py export --snapshot <entry> --mode source --output <new.zip>
python <skill>/scripts/handoff.py export --snapshot <entry> --mode baseline --output <new.zip>
python <skill>/scripts/handoff.py restore --archive <zip> --target <empty-dir> --dry-run
python <skill>/scripts/handoff.py restore --archive <zip> --target <empty-dir> --apply
```

baseline 模式另需 `--baseline <本地Git仓库>`，核对精确基线对象；不会自行 fetch。当前实现为保证原快照可独立核验，baseline ZIP 也携带完整快照，因此不是体积最小的 delta。
source 模式不依赖原工作区。保留原 HEAD commit，作为浅历史边界；不保留完整提交历史、refs 集合或 reflog。若要 Git bundle 属于另行实现的增强。
默认只生成本地文件，不上传。`--apply` 表示执行意图，不替代宿主文件权限或用户范围授权。已有用户授权足够时直接执行计划，无需机械重复确认。

流程是 ZIP 清单与配额检查 → 私有临时目录解包 → 全部哈希/版本/引用核验 → 路径/链接/目标/基线检查 → 计划 → 目标同级临时目录重建 → HEAD/index/字节校验 → 发布到空目标。
目标必须不存在或完全为空，现存业务目录绝不覆盖。导入不运行任何项目命令或附件。失败清理仅针对恢复器自己创建的临时目录；不删除目标数据。

以下会阻断完整恢复，并在包中留事实：敏感/超大必需文件排除；未递归子模块/嵌套仓库；缺实际内容的 LFS pointer；冲突 stages 或 merge/rebase/cherry-pick/revert/sequencer 状态；skip-worktree/assume-unchanged；Git SHA-256 对象格式。
Linux 可恢复范围内的相对符号链接，越界目标拒绝。Windows 第一版不自动创建链接/junction，明确返回不支持。原始 CRLF 字节保留，Git 对象单独核验。
默认声明范围不包含未显式选择的 ignored 文件、未跟踪缓存/构建/依赖目录、环境变量值、远程服务与数据库。

## 失败事务

inspect 指出未发布 `.staging` 事务与不在 CURRENT 祖先链上的孤立 snapshot。不要把它们自动当作 CURRENT。
草稿经过过滤；修正 context 后重新 save。若孤立包是所需结果，先 verify 再显式用其路径接手，保留 CURRENT 的原子发布约束。
写锁含随机 token、pid、host 和时间。不要因时间过久删除；同主机确认 PID 已终止、核对事务没有其他写者，再由有权限的操作者处理具体锁文件。无法证明持有者失效则保留锁并说明影响。
不做自动历史清理。CURRENT/被引用/尚未迁移的恢复材料不可随意删除。

## 已知边界

- 双读一致性不是操作系统快照，捕获后仍可能有新写入。
- 敏感检测是启发式；未知格式、编码和二进制嵌入的秘密可能无法识别。不要纳入高风险材料。
- 非 UTF-8、Windows 不兼容名字、大小写冲突均不能宣称跨平台恢复成功。
- Windows 长路径环境有差异；深目录可指定较短的外部 `--store`。不会修改系统长路径设置。
- identity 与哈希不认证来源，导入包作为数据处理。
- 原始聊天、未保存缓冲区、进程内存、凭据与外部服务不在恢复承诺内。
