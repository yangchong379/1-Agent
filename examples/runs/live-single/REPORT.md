# 已核查的真实模型冲突案例

这是最初单案例运行的历史核查报告，以下范围判断保留当时状态。后续首轮13组真实评估及失败复核见[最新评估文档](../../../docs/03-evaluation.md)。

2026-11-04 15:12:20（香港时间），用户在本机运行一键脚本并输入密钥。运行模式为 `live_model`，模型 `deepseek-flash`，共5次模型/工具调用。助手随后读取原始 Trace 并以只读方式核对本地 SQLite 数据库。

- [未经改写的实际结果与 Trace](../live-conflict.json)
- [核查项及原始文件 SHA-256](summary.json)
- [实际数据库快照](database_snapshot.json)

| 步骤 | 模型选择动作 | 工具实际观察 | 后续动作 |
|---|---|---|---|
| 1 | read_material({}) | M01元数据完整、没有已有草稿 | check_rules |
| 2 | check_rules({}) | approved，无缺失与风险 | query_slots |
| 3 | query_slots({}) | 18:00占用；17:00、19:00、20:00可用 | 选择19:00保存草稿 |
| 4 | save_draft(slot=19:00) | CREATED，pending_user，返回草稿ID | finish |
| 5 | finish({}) | awaiting_confirmation | 结束 |

模型在第4步给出的简要行动依据指出，18:00已占用，因此选择最近的较晚可用时间19:00，硬性时间变更须待用户确认。工具回执和数据库均为 `pending_user`，原要求仍为18:00，`published=false`。

**结论：这一条真实模型工具循环通过核查。** 尚未补齐第二条不同工具结果下的真实路径或完整真实场景评估，不能把单案例成功扩展为整体通过率或全部达标。

下一步：`py -3.11 scripts/connect_deepseek.py --evaluate`，在本机密码窗口重新输入密钥，完成13组真实场景并保留失败记录。该命令会产生多次付费API调用。初始单案例的数据库和原始结果会保留。
