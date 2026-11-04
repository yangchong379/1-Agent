# 03 测试、实际结果和限制

## 已实际执行的验证

环境：Windows、Python 3.11.4、标准库 sqlite3。执行命令：

```bash
python -m unittest discover -s tests -v
python scripts/evaluate.py
```

**实际结果：42 个自动化测试全部通过，13/13 组离线场景断言通过。** 精确执行时间、源码 SHA-256、平台、逐项检查见 [summary.json](../examples/runs/mock/summary.json)，测试名称与结果见 [tests.txt](../examples/runs/mock/tests.txt)。这些是运行代码产生的文件，不是人工编造的日志。时间戳使用 UTC；人类交接时间使用香港时间 UTC+8。

**真实模型：未运行。** 用户提供官方平台链接后，已核对 Base URL 为 `https://api.deepseek.com`、DeepSeek V4.1 Flash 的 API model 为 `deepseek-flash`；本机密钥尚未配置，因此无法证明真实模型在不同观察下能调整动作。不提交准确率、模型效果分数或“已满足真实 ReAct 验收”的结论。型号依据见[官方模型列表](https://api-docs.deepseek.com/quick_start/pricing/)。

## 逐场景预期与实际

下表均是 `offline_mock`，工具、SQLite 写入及回滚是真实执行。每个场景目录包含输入、完整合成数据、实际结果/Trace 和数据库快照，可独立复现。

| 场景 | 预期 | 实际 | 记录 |
|---|---|---|---|
| 正常 | 审核通过、17:00 草稿保存 | draft_ready，17:00，1 份草稿 | [normal](../examples/runs/mock/normal/result.json) |
| 信息不足 | 补查无结果，停止保存 | needs_info，缺标题和版权，0 份草稿 | [missing](../examples/runs/mock/missing/result.json) |
| 规则风险 | 禁用宣传表述阻断 | blocked，PROHIBITED_CLAIM，0 份草稿 | [risk](../examples/runs/mock/risk/result.json) |
| 时间冲突 | 要求18:00，被占用后建议19:00待确认 | awaiting_confirmation，原要求未改 | [conflict](../examples/runs/mock/conflict/result.json) |
| 重复提交 | 两次结果同草稿 ID，只有1条记录 | 第二次 DUPLICATE，1 份草稿 | [第一次](../examples/runs/mock/duplicate/first_run.json)、[第二次](../examples/runs/mock/duplicate/result.json)、[快照](../examples/runs/mock/duplicate/database_snapshot.json) |
| 保存失败 | 两次尝试都失败，事务回滚 | save_failed，无 ID，0 份草稿 | [save_failure](../examples/runs/mock/save_failure/result.json) |
| 补查成功 | M02 补齐版权后重审并继续 | draft_ready，17:00 | [supplement](../examples/runs/mock/supplement/result.json) |
| 用户明确同意 | 精确同意19:00更新原草稿 | draft_ready，UPDATED，ID不变，1 份草稿 | [confirmed](../examples/runs/mock/confirmed/result.json) |
| 更换占用并重复 | 18:00及19:00占用后选20:00，重复去重 | 20:00待确认，重复仍1份 | [changed_occupancy](../examples/runs/mock/changed_occupancy/result.json) |
| 时段耗尽 | 没有候选时段则停止 | no_available_slot，0 份草稿 | [no_slots](../examples/runs/mock/no_slots/result.json) |
| 步数耗尽 | 2轮后明确未完成 | incomplete_step_limit，model_calls=2 | [step_limit](../examples/runs/mock/step_limit/result.json) |
| 多素材 | 分配不同时间且各自保留确认边界 | M01 17:00，M06 19:00待确认，2份草稿 | [batch](../examples/runs/mock/batch/result.json) |
| 版权与隐私风险 | 两个原因都返回并阻断 | COPYRIGHT_DENIED + PRIVACY_RISK，0份 | [privacy_copyright](../examples/runs/mock/privacy_copyright/result.json) |

## 观察如何影响后续动作

以下是对实际 Trace 的摘要，不是预先写给模型的动作列表；完整参数、结果和依据在对应 JSON 中。

1. [正常路径](../examples/runs/mock/normal/result.json)：read_material → check_rules(approved) → query_slots(17:00可用) → save_draft(17:00, CREATED/confirmed) → finish。
2. [缺资料路径](../examples/runs/mock/missing/result.json)：read_material → check_rules(needs_info) → supplement_metadata(found={}) → check_rules(仍缺资料) → finish；没有执行查询或保存。
3. [补查成功路径](../examples/runs/mock/supplement/result.json)：check_rules(needs_info) → supplement_metadata(查到licensed) → check_rules(approved) → query_slots → save_draft → finish。
4. [保存故障路径](../examples/runs/mock/save_failure/result.json)：save_draft(SAVE_FAILED) → save_draft(SAVE_FAILED) → finish(save_failed)；数据库快照草稿数量为0。
5. [占用变化路径](../examples/runs/mock/changed_occupancy/first_run.json)：query_slots 显示18:00和19:00占用，save_draft选择20:00；默认冲突场景中19:00可用，因此选19:00。

单元测试还在首次查询后注入新的占用，实际验证 `save_draft(SLOT_CONFLICT) → query_slots → save_draft(替代时间) → finish`。这一行为由 Mock 根据观察选择，真实模型是否也会这样做仍需 live Trace。

## 额外工程检查

[test_agent.py](../tests/test_agent.py) 覆盖两个连接并发去重、不同素材并发抢同一时段、半开区间边界、保存时重新核查、用户批准精确范围、批准更新失败回滚、旧请求不能降级已确认状态、越权工具/伪造确认参数拒绝、未经审核或查询不能保存、未知素材、输入类型及时区校验、请求 ID 复用冲突、CLI 各退出码、模型协议错误及认证错误脱敏。

真实适配器单元测试使用伪造 HTTP 响应，验证了原 tool-call ID、tool observation 和思考字段内存回传，不是远端接口实测，不能当作真实模型成功记录。GitHub Actions 配置已提供，但尚未推送，因此**未声称云端 CI 已通过**。

## 失败与已知限制

- 故障注入证明本地失败处理；不覆盖真实网络抖动、平台权限、平台限流或服务端“已提交但响应丢失”的复杂情况。
- 不支持持续同步真实已有排期；数据集变更会要求使用新数据库。运行内并发写入由事务保护，但跨业务系统的一致性尚未实现。
- 同素材/渠道唯一活动草稿，不支持活动版本、撤销、自动过期和对旧草稿更改原始要求。
- 待确认草稿也占时段，需要后续加入超时释放，否则可能降低可用时段数量。
- 元数据审核不是多媒体内容理解；合成版权字段并非真实版权证据。
- CLI 用户输入被视作可信批准来源；没有多人权限认证或审批签名。模型无法自授批准权限，但多人产品需另加认证。
- 模型可能选较差但合法的时段、提前请求用户补充、达到预算或返回不合规调用。工具限制能防越权，不能保证模型任务完成率。
- 当前固定日期和固定偏移服务于可复现测试；不是实时发布建议，也不证明其它时区或跨日能力。

## 补齐真实模型验证

配置后执行 `python scripts/evaluate.py --model live --output examples/runs/live`，至少人工审阅 normal、missing、risk、conflict、duplicate、save_failure 场景。模型可有不同工具顺序；不能仅靠预期文本相同判断正确。检查其是否看到工具观察、是否在冲突后选择合法替代、是否保留待确认、是否如实报告保存失败。提交 live 原始 Trace、摘要和失败原因后再更新本文件的结论。自动报告中的 `real_model_decision_quality_verified=false` 需由人工核查记录解释，不能自动改成通过。
