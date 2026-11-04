# 考核提交入口

- 题号：**1 · 素材审核与发布排期 Agent**
- GitHub URL：[yangchong379/1-Agent](https://github.com/yangchong379/1-Agent)
- 分支：`main`
- 完整 commit SHA：以本次 GitHub 提交页面显示的40位 SHA 为准；本地可运行 `git rev-parse HEAD` 核对。
- 运行与评审：[README.md](README.md)
- 已执行验证：54个自动化测试通过、13组离线场景通过；首轮真实 DeepSeek 评估13组，8通过、5失败。
- 真实路径证据：[原始Trace](examples/runs/live-conflict.json)、[核查报告](examples/runs/live-single/REPORT.md)。

完整首轮真实评估见[复核报告](examples/runs/live/REVIEW.md)，已覆盖正常、资料不足、风险等不同观察下的真实动态路径；仍有5项待修复后真实重跑，不能声称全部验收已通过。原始失败保留，代码修复已通过回归测试。后续新增验证材料后须提交更新版本并使用新的最终SHA。

代码、文档和测试由AI助手辅助生成；用户已实际执行真实模型案例。个人贡献及待补记录见 [AI使用说明](docs/04-ai-usage.md)。仓库不包含真实密钥、运行时数据库或真实隐私数据。
