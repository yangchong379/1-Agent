# 考核提交入口

- 题号：**1 · 素材审核与发布排期 Agent**
- GitHub URL：[yangchong379/1-Agent](https://github.com/yangchong379/1-Agent)
- 分支：`main`
- 完整 commit SHA：以本次 GitHub 提交页面显示的40位 SHA 为准；本地可运行 `git rev-parse HEAD` 核对。
- 运行与评审：[README.md](README.md)
- 已执行验证：55个自动化测试通过、13组离线场景通过；真实 DeepSeek 首轮8/13通过，修复后失败项重跑5/5通过。
- 真实路径证据：[原始Trace](examples/runs/live-conflict.json)、[核查报告](examples/runs/live-single/REPORT.md)。

首轮、修复后重跑与输入/输出/Trace的验收映射见[累计复核](examples/runs/LIVE-REVIEW.md)。跨版本累计13个场景均有通过记录，首轮失败原样保留；这不是当前源码单次全量13/13或稳定成功率。保存后重读的审核显示修正仅做了离线回归，没有用改写的JSON冒充新实测。后续新增验证材料后须提交更新版本并使用新的最终SHA。

个人贡献包括需求与验收推进、业务边界核对、本机模型接入、真实评估执行、失败反馈、修复后复测和仓库交付协作，详见[个人贡献说明](docs/07-personal-contributions.md)。代码与自动化测试由AI协助实现，分工见[AI使用记录](docs/04-ai-usage.md)。仓库不包含真实密钥、运行时数据库或真实隐私数据。

本轮真实结果：真实连续请求24条，业务目标完成9条，边界检查24/24，见README新增入口；原始失败保留。
