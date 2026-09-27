# 已验证范围

开发时在 Windows 11（Python 3.12.4、Git 2.33.1）和 WSL Ubuntu 26.04（Python 3.14.4、Git 2.53.0）运行了 26 项集成测试：Windows 25 项通过，1 项 POSIX 文件名与链接测试跳过；Linux 26 项全部通过。Windows 包在 Linux、Linux 包在 Windows 均完成实际恢复并得到相同源码指纹。Skill 格式校验通过。这里只记录可公开复现的结果，不附带原机器路径和安装日志。

主要已测场景包括：同文件不同的暂存与未暂存字节、未跟踪二进制、删除、无 Git/无 HEAD、detached HEAD、真实 merge 冲突、子模块 gitlink 与 LFS pointer 标记、保存故障与硬崩溃后旧 CURRENT 有效、锁冲突、错项目/基线、接手漂移与测试时效、敏感信息排除、ZIP 路径穿越和压缩限制、五次连续交接，以及源码包脱离原目录恢复。

运行 `python project-handoff/tests/run_checks.py --report test-results.json` 可在当前平台复验。CI 配置会在 GitHub 托管的 Windows/Ubuntu runner 上运行；**首次发布前没有 GitHub Actions 的实际运行记录**。

仍未完成的验收：由两个真正独立的对话执行“前一位 agent 保存、后一位 agent 仅凭 Skill/项目/包完成下一步”；未独立确认新会话的技能自动发现。生成接力 fixture 的脚本在 `project-handoff/tests/make_example.py`，含接手提示和只给验收者的标准。单机恢复测试不能替代 agent 接力验收。

恢复能力限制见 [recovery.md](../project-handoff/references/recovery.md)。测试结果只证明这些 fixture 中没有观察到无意覆盖或字节不一致，不对未知环境作普遍保证。
