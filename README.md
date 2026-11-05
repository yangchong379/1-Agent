# 素材审核与发布排期 Agent · 题目 1

帮助内容团队审核素材、查询无冲突时段、保存可供用户确认的排期草稿。**只保存草稿，项目中不存在发布接口。**

时段查询失败时，执行器立即结束当前素材并返回 `query_failed`。批次继续处理其余素材。服务恢复后可以用原请求重试。用原始 007 和 019 请求、故障设置及前置快照进行离线回放，两条记录分别在 6 轮和 3 轮结束，已有草稿未被覆盖。[回归记录](examples/regressions/query-failure.json)

**核心历史验证状态：55个自动化测试通过，13组离线场景通过；首轮真实 DeepSeek 评估8/13通过，修复后五个失败项重跑5/5通过。** 首轮失败和重跑均保留，[累计13场景证据及复核](examples/runs/LIVE-REVIEW.md)覆盖全部验收点，但这是跨版本累计记录，不是当前版本单次全量13/13或稳定成功率。另已修正保存后重读导致审核状态显示为unchecked的问题，并以实际路径做离线回归；该展示修正未新增模型调用。项目仓库：[yangchong379/1-Agent](https://github.com/yangchong379/1-Agent)。Mock不作为真实模型决策证明。

## 个人贡献与AI协作

候选人承担需求与验收推进、关键业务边界核对、Windows本机模型接入、真实评估执行、失败反馈和修复后复测，并创建目标仓库、完成登录授权。AI协助完成代码与测试实现、源码级问题定位、材料整理和Git推送。具体职责及对应证据见[个人贡献说明](docs/07-personal-contributions.md)与[AI使用记录](docs/04-ai-usage.md)。

## 评审入口

| 材料 | 入口 |
|---|---|
| 实际离线结果与完整 Trace | [examples/runs/mock/REPORT.md](examples/runs/mock/REPORT.md) |
| 已核查的真实冲突路径 | [examples/runs/live-single/REPORT.md](examples/runs/live-single/REPORT.md) |
| 首轮完整真实评估与失败复核 | [examples/runs/live/REVIEW.md](examples/runs/live/REVIEW.md) |
| 修复后重跑与跨版本累计复核 | [examples/runs/LIVE-REVIEW.md](examples/runs/LIVE-REVIEW.md) |
| 测试执行明细 | [examples/runs/mock/tests.txt](examples/runs/mock/tests.txt) |
| 结构化结果、环境、源码摘要 | [examples/runs/mock/summary.json](examples/runs/mock/summary.json) |
| 需求及验收映射 | [docs/01-requirements.md](docs/01-requirements.md) |
| 模型循环、确认边界和幂等设计 | [docs/02-solution.md](docs/02-solution.md) |
| 效果评估与未验证范围 | [docs/03-evaluation.md](docs/03-evaluation.md) |
| AI 使用及个人贡献说明 | [docs/04-ai-usage.md](docs/04-ai-usage.md) |
| 个人职责、验证操作与产物对照 | [docs/07-personal-contributions.md](docs/07-personal-contributions.md) |
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

**最简方式（推荐）：** 在本机 PowerShell 只复制下面一行命令，不要复制 `PS E:\...>`、`>>` 或星号。脚本会自动配置官方接口，并提示你在本机隐藏输入密钥，无需手工设置环境变量。

```powershell
py -3.11 scripts/connect_deepseek.py
```

Windows 下会弹出密码输入窗口：点击输入框，按 Ctrl+V 粘贴实际密钥，再点 OK。窗口以星号显示输入，支持正常粘贴；不要自己输入星号。Windows 入口需要 Python 自带的 tkinter（本机已确认可用）；非 Windows 仍使用终端隐藏输入。脚本仅运行一次冲突案例，最多12步，使用真实 API 额度；凭据只存在于该进程内，不写入文件。真实结果保存为 `examples/runs/live-conflict.json`。如果密钥曾发到聊天或公开位置，请先在平台撤销并重新创建。本机已成功运行一次真实冲突案例；完整评估使用同样的密码框，只需再次运行：

```powershell
py -3.11 scripts/connect_deepseek.py --evaluate
```

该命令在临时数据库中执行13组真实场景，会进行多次付费 API 调用，记录保存到 `examples/runs/live/`，不会改变之前单案例的草稿。每个场景完成会打印 PASS/FAIL；请保持窗口打开直到结束。脚本自动断言通过后仍须人工核查实际 Trace。

第一轮完整评估结束后，修复代码并只补跑失败项可使用：

```powershell
py -3.11 scripts/connect_deepseek.py --retry-failed
```

该命令从第一轮 `summary.json` 选择失败场景，把新结果写到独立的 `examples/runs/live-retry-N/`，保留原始失败结果。没有失败项时不会请求密钥或调用模型。请不要用重新执行 `--evaluate` 覆盖需要保留的第一轮证据。

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

题号：**1 · 素材审核与发布排期 Agent**。GitHub URL：[https://github.com/yangchong379/1-Agent](https://github.com/yangchong379/1-Agent)。完整提交 SHA 可执行 `git rev-parse HEAD` 获取，并与 GitHub 最新提交核对。后续补跑真实模型、补记候选人实际贡献并提交后，应使用更新后的最终 SHA。详见 [交接说明](docs/06-handoff.md)。

## 连续混合需求评估（新增）

新增两天、两个随机种子的连续需求回放，共96条请求；同一天所有到达共用一个SQLite数据库，每次到达重新连接。实际业务目标完成22/96，边界和状态检查96/96。这些是Mock离线结果，不能证明真实模型线上完成率。[流量评估说明](docs/08-product-traffic.md)、[第1天实际记录](examples/traffic/mock-product-day1/REPORT.md)、[第2天实际记录](examples/traffic/mock-product-day2/REPORT.md)、[当轮57个回归测试](examples/traffic/regression-tests.txt)。

```bash
python scripts/traffic.py --model mock --count 48 --seed 20261104 --output .runtime/traffic-new
# 配置模型环境变量后使用真实选择：
python scripts/traffic.py --model live --count 24 --seed 20261104 --output .runtime/live-traffic-new
```

每条记录包含输入、实际输出/Trace、前后全量状态；没有预设“每类必须成功”的理想动作路径。未完成与保护检查通过分开计数；历史验收记录不覆盖，历史源码摘要属于当时src/tests/scripts集合。本次新增评估脚本和测试改变整体摘要，运行src与上次交付基线逐字相同。

## 本轮真实模型记录

真实连续请求24条，业务目标完成9条，边界检查24/24。[实际原始结果与AI复核](examples/traffic/live-20261104-20261105-004121-535187/REVIEW.md)。运行代码和数据边界不变，失败不改写；实际状态与质量限制以该报告为准。
