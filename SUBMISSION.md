# 考核提交入口

- 题号：**1 · 素材审核与发布排期 Agent**
- GitHub URL：[yangchong379/1-Agent](https://github.com/yangchong379/1-Agent)
- 分支：`main`
- 完整 commit SHA：以本次 GitHub 提交页面显示的40位 SHA 为准；本地可运行 `git rev-parse HEAD` 核对。
- 运行与评审：[README.md](README.md)
- 已执行验证：45个自动化测试、13组离线场景；1条真实 DeepSeek 冲突路径。
- 真实路径证据：[原始Trace](examples/runs/live-conflict.json)、[核查报告](examples/runs/live-single/REPORT.md)。

当前尚未完成完整真实模型评估，也尚未补齐至少两种不同工具观察下的真实模型路径。请如实使用上述验证范围，不能把离线 Mock 视为真实模型决策证明。后续新增验证材料后须提交更新版本并使用新的最终 SHA。

代码、文档和测试由AI助手辅助生成；用户已实际执行真实模型案例。个人贡献及待补记录见 [AI使用说明](docs/04-ai-usage.md)。仓库不包含真实密钥、运行时数据库或真实隐私数据。
