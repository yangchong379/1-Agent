# 06 接口配置与 GitHub 提交交接

## 给尚未配置过 API 的使用者

API 是程序调用模型的入口；网页聊天权限不一定包含 API 权限。你需要向提供“DeepSeek 4.1”服务的平台查到：

| 名称 | 意思 | 从哪里找 |
|---|---|---|
| Base URL | API 根地址，代码将追加 /chat/completions | 平台的 API 接入说明 |
| model | 请求中填写的准确模型编号，不一定等于网页展示名 | 平台的模型列表/调用示例 |
| API Key | 你账号调用接口的密钥 | 平台的密钥管理页；不发给聊天，不提交Git |
| MODEL_API_KEY | 本项目选择的环境变量名字，用于在本机存放 API Key | 由项目规定，不需要从平台找 |

用户已提供 [DeepSeek 官方密钥管理页](https://platform.deepseek.com/api_keys)。2026-11-04 核对[官方首次调用说明](https://api-docs.deepseek.com/)和[模型列表](https://api-docs.deepseek.com/quick_start/pricing/)，本项目可按以下配置接入 V4.1 Flash：`MODEL_BASE_URL=https://api.deepseek.com`、`MODEL_NAME=deepseek-flash`。本机仍需设置 `MODEL_API_KEY`。官方管理页需用户自行登录；助手未访问账户中的密钥、余额或权限。不要发送密钥，也不要把后台含密钥的截图放入仓库。项目没有自动扫描电脑寻找密钥。

README 给出当前终端安全读取密钥的 PowerShell 命令。环境变量只影响当前终端及其子进程；在其它终端运行时需要重新配置。程序不会自动读取 `.env`，不要以为复制 `.env.example` 就已完成接入。

也可直接运行 `py -3.11 scripts/connect_deepseek.py`。该脚本自动配置官方接口、隐藏读取新密钥、运行真实冲突案例并还原进程内环境。只复制命令文字，不复制终端显示的 `PS ...>`、`>>` 或密钥掩码星号。看到 `>>` 时先按 Ctrl+C 退出未完成的多行输入，再重试。已公开或发到聊天里的密钥应在平台撤销后重新创建。

## 真实模型验收建议

先单独跑冲突案例，再运行完整评估。`--model live` 失败不会切回 Mock。检查生成文件中 `mode=live_model`、实际工具调用、返回观察、后续动作；人工复核至少两条因不同观察而改变后续动作的路径。

把 `examples/runs/live/summary.json` 和原始结果提交 Git，并更新 `docs/03-evaluation.md` 与 AI 使用说明。报告模型准确 ID、提供方、运行日期、失败/成功情况，不提交密钥、账单或私人账户信息。自动断言通过只证明这些案例满足业务条件，不能代替审阅真实模型行为。

## 数据变化复现

每个已记录场景都带 `dataset.json`。可直接用变更占用场景的数据重新运行：

```bash
python scripts/run.py --input examples/inputs/changed_occupancy.json --data examples/runs/mock/changed_occupancy/dataset.json --db .runtime/changed.sqlite --output .runtime/changed-1.json
python scripts/run.py --input examples/inputs/changed_occupancy.json --data examples/runs/mock/changed_occupancy/dataset.json --db .runtime/changed.sqlite --output .runtime/changed-2.json
```

该数据将18:00和19:00都设为占用，Mock 建议20:00，重复后仍一份草稿。修改数据后须换一个数据库路径；程序拒绝把已有数据库绑定到不同数据集，避免静默破坏原草稿。

## GitHub 交付

当前没有目标仓库地址，没有推送或创建远程仓库。本地仓库已有 AI 初稿提交，可在仓库目录执行：

```bash
git log -1 --oneline
git rev-parse HEAD
```

你可在 GitHub 新建一个空仓库（不要预建 README），然后在本地仓库中执行：

```bash
git remote add origin https://github.com/你的账号/你的仓库.git
git push -u origin main
```

若从不含 `.git` 的源码 ZIP 开始，则先 `git init -b main`，配置自己的真实 Git 作者身份，`git add .`，`git commit -m "Add draft-only scheduling agent"`，再添加远程并推送。也可从交付的 Git bundle 保留 AI 初稿历史：

```bash
git clone material-scheduling-agent.bundle material-scheduling-agent
```

候选人完成真实修改和验证后，应以自己的真实 Git 身份提交新增工作，并如实保留 AI 使用范围。私有仓库要添加考核指定评审账号的读取权限；本轮未提供评审账号，不能代填。

最终提交信息模板：

```text
题号：1 素材审核与发布排期 Agent
GitHub URL：填写实际仓库 URL
最终 commit SHA：运行 git rev-parse HEAD 后填写完整40位SHA
真实模型验证：填写已验证模型及报告路径，或如实注明尚未验证
```

ZIP/bundle 交付时的 SHA 只是初稿版本；后续新增真实 Trace 或个人修改后，必须提交新的最终 SHA。不要使用示例仓库 URL 或把本地路径称为 GitHub URL。
