# 素材审核与发布排期 Agent · 题目 1

帮助内容团队审核素材、查询无冲突时段、保存可供用户确认的排期草稿。**只保存草稿，项目中不存在发布接口。**

**当前交付状态：离线工程验证已完成；DeepSeek 官方地址及模型编号已核对，本机尚未配置密钥，真实模型决策效果未验证。GitHub 仓库尚未创建/推送。** 不能把 Mock Trace 作为满足模型驱动 ReAct 的证据；提交前须执行真实模型验证并审核记录。

## 评审入口

| 材料 | 入口 |
|---|---|
| 实际离线结果与完整 Trace | [examples/runs/mock/REPORT.md](examples/runs/mock/REPORT.md) |
| 测试执行明细 | [examples/runs/mock/tests.txt](examples/runs/mock/tests.txt) |
| 结构化结果、环境、源码摘要 | [examples/runs/mock/summary.json](examples/runs/mock/summary.json) |
| 需求及验收映射 | [docs/01-requirements.md](docs/01-requirements.md) |
| 模型循环、确认边界和幂等设计 | [docs/02-solution.md](docs/02-solution.md) |
| 效果评估与未验证范围 | [docs/03-evaluation.md](docs/03-evaluation.md) |
| AI 使用及个人贡献说明 | [docs/04-ai-usage.md](docs/04-ai-usage.md) |
| 复盘及实际用时 | [docs/05-retrospective.md](docs/05-retrospective.md) |
| 模型配置与 GitHub 提交流程 | [docs/06-handoff.md](docs/06-handoff.md) |

## 环境与运行

Python **3.11+**，仅使用标准库；SQLite 随 Python 提供，无第三方运行或测试依赖，无须安装 Agent 框架。Windows 可将下文 `python` 替换为 `py -3.11`。所有命令在本仓库根目录执行。

```bash
python --version
# 无需 pip install，即可运行：
python scripts/run.py --input examples/inputs/normal.json --db .runtime/normal.sqlite --output .runtime/normal.json
python scripts/run.py --input examples/inputs/conflict.json --db .runtime/conflict.sqlite --output .runtime/conflict.json
python -m unittest discover -s tests -v
python scripts/evaluate.py
```

可选安装：`python -m pip install -e .`，然后用 `material-agent` 或 `python -m scheduling_agent` 代替 `python scripts/run.py`。`.env.example` 是配置说明，程序**不会自动加载** `.env`。

离线模式默认启用，不需要密钥。评估脚本为每个场景创建临时数据库，执行后记录数据库快照，因此可重复运行，不受日常 CLI 草稿影响。再次运行 CLI 且复用同一个 `--db` 可验证跨进程幂等；更换数据文件需使用新的数据库路径，程序不会静默重置原库。

```bash
# 同一数据库重复两次，只保留一份草稿，第二次返回 DUPLICATE
python scripts/run.py --input examples/inputs/conflict.json --db .runtime/repeat.sqlite --output .runtime/first.json
python scripts/run.py --input examples/inputs/conflict.json --db .runtime/repeat.sqlite --output .runtime/second.json
# 人工模拟保存失败，预期退出码 2，JSON 中 save_failed，数据库无新增草稿
python scripts/run.py --input examples/inputs/normal.json --db .runtime/failure.sqlite --fault save_draft --output .runtime/failure.json
```

| 退出码 | 意义 |
|---|---|
| 0 | 每项草稿均已保存；仍可能存在待用户确认项，不代表发布 |
| 2 | 已完成本轮处理，但至少一项未保存：缺资料、风险、无时段、保存失败或要求冲突 |
| 3 | 未完成：全请求步数达到上限或模型调用失败；已成功保存的部分会如实保留 |
| 4 | 输入、环境配置、文件或数据库初始化错误 |

## 输入与输出

```json
{
  "request_id": "demo-18",
  "material_ids": ["M01"],
  "channel": "douyin",
  "preferred_slot": "2026-11-05T18:00+08:00",
  "hard_time": true,
  "approved_slots": {}
}
```

`request_id` 同值须对应同一请求内容，修改请求须使用新 ID。时间必须显式带 `+08:00`，不依赖电脑时区。`hard_time=true` 时，替代时间只形成待确认草稿；只有由 CLI 用户输入的 `approved_slots` 精确授权某素材、某时段后，才确认该替代时间。所有确认均只针对草稿。

例：M01 要求 18:00，已有排期占用 18:00–19:00，查询后建议 19:00。输出的 `requested_slot` 仍为 18:00，`suggested_slot` 为 19:00，`status=awaiting_confirmation`，`save_receipt.confirmation=pending_user`，`published=false`。用户同意后，在新请求中填写 `"approved_slots":{"M01":"2026-11-05T19:00+08:00"}` 并换一个 `request_id`，复用数据库可更新原草稿，不新增第二份。

输出 JSON 含每项审核状态、风险原因、缺失字段、建议时段、待确认项、保存回执及 Trace。每条 Trace 含步骤、素材、动作、参数、简短依据、实际工具返回和下一步动作。`execution_complete` 仅表示循环已结束；是否保存必须检查 `draft_save_status`/`all_drafts_saved`，是否需要确认还要检查 `pending_confirmation`。

## 真实模型运行

适配实现使用 Chat Completions function calling，可配置 DeepSeek 或提供该协议的服务。用户已提供 DeepSeek 官方平台链接；2026-11-04 核对官方文档，`deepseek-flash` 对应 DeepSeek-V4.1-Flash-1017，根地址为 `https://api.deepseek.com`。此处是官方型号映射，并非远端调用成功记录。依据：[DeepSeek 首次调用](https://api-docs.deepseek.com/)、[模型列表](https://api-docs.deepseek.com/quick_start/pricing/)、[DeepSeek Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)、[OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)。

PowerShell 安全配置示例：

```powershell
$env:MODEL_BASE_URL = 'https://api.deepseek.com'
$env:MODEL_NAME = 'deepseek-flash'
$modelSecret = Read-Host 'API Key（仅保存在当前进程环境）' -AsSecureString
$env:MODEL_API_KEY = [System.Net.NetworkCredential]::new('', $modelSecret).Password
# 官方 DeepSeek 支持该参数；先以非思考模式验证工具循环
$env:MODEL_THINKING = 'disabled'
py -3.11 scripts/run.py --model live --input examples/inputs/conflict.json --db .runtime/live-conflict.sqlite --output examples/runs/live-conflict.json
# 完整真实模型评估会进行多次付费模型调用；仅在确认配置后由你执行
py -3.11 scripts/evaluate.py --model live --output examples/runs/live
Remove-Item Env:MODEL_API_KEY
```

Base URL 不含 `/chat/completions`，代码会拼接该路径；密钥来自环境变量，不能写入输入文件、代码、截图或仓库。仅当使用 DeepSeek **官方直连接口**时，官方文档示例的根地址为 `https://api.deepseek.com`；中转服务、云平台可能使用完全不同的 URL 和模型编号，必须以你的服务商文档为准。参见 [官方工具调用示例](https://api-docs.deepseek.com/guides/tool_calls/)。

真实模式中，每一步动作由模型返回的工具调用决定，应用执行工具并把真实观察回传模型；没有预设模型动作列表，也不会在模型失败时偷偷切回 Mock。模型协议错误返回 `incomplete_model_error`，HTTP 错误不记录服务端响应体。详见 [方案](docs/02-solution.md)。

## 当前限制

资料、规则和业务工具均为本地合成数据；审核是可解释规则检查，不含图像/视频识别。只处理固定 `+08:00` 日期内的 60 分钟候选时段，不支持自然语言需求解析、跨日排期或真实发布。每个渠道、每份素材仅保留一份活动草稿；待确认草稿会暂占时段，本版本不含撤销和过期机制。CLI 输入者视为授权用户，尚未实现多人身份认证；上线前必须为批准操作增加身份和审计校验。

## GitHub 提交

题号：**1 · 素材审核与发布排期 Agent**。当前 GitHub URL：**未提供，未推送**。本地提交 SHA 可执行 `git rev-parse HEAD` 获取。推送、补跑真实模型、补记候选人实际贡献后，按 [交接说明](docs/06-handoff.md) 提交最终 URL 与最终 SHA。
