# 03 测试、实际结果和限制

## 已实际执行的验证

环境：Windows、Python 3.11.4、标准库 sqlite3。执行命令：

```bash
python -m unittest discover -s tests -v
python scripts/evaluate.py
```

**实际结果：55 个自动化测试全部通过，13/13 组离线场景断言通过。** 精确执行时间、源码 SHA-256、平台、逐项检查见 [summary.json](../examples/runs/mock/summary.json)，测试名称与结果见 [tests.txt](../examples/runs/mock/tests.txt)。这些是运行代码产生的文件，不是人工编造的日志。时间戳使用 UTC；人类交接时间使用香港时间 UTC+8。

**真实模型：首轮完整13组已执行，8/13通过、5项失败。** 模型为 `deepseek-flash`，真实模型决策配合本地合成业务工具，耗时988.813秒。正常、信息不足、风险、补查成功、明确批准、无时段、步数上限及版权隐私风险通过；冲突、保存故障、重复提交、变更占用后重复、批量场景未全部通过。见[原始summary](../examples/runs/live/summary.json)、[逐项复核](../examples/runs/live/REVIEW.md)。已有至少两条不同工具观察下的真实决策路径，但不能据此声称完整真实验收通过。最初单次冲突成功记录也保留在[live-conflict.json](../examples/runs/live-conflict.json)。

**修复后只补跑上述5项，5/5通过，耗时425.734秒。** [重跑原始summary](../examples/runs/live-retry-1/summary.json)、[累计复核](../examples/runs/LIVE-REVIEW.md)、[逐项检查与文件摘要](../examples/runs/live-comparison.json)均保留。13个场景跨修复前后版本均有通过记录，不将其表述为当前源码单次全量13/13或模型稳定成功率。模型是真实调用，保存故障由本地工具故障注入，业务素材/规则为合成数据。

原始JSON按字节保留，`.gitattributes`禁止Git对`examples/`下JSON自动转换换行，确保报告中的SHA-256可在远端检出后核对。该设置不改变输入、输出或Trace内容。

| 真实验收点 | 输入 | 实际输出及Trace |
|---|---|---|
| 正常排期 | [input](../examples/runs/live/normal/input.json) | [result](../examples/runs/live/normal/result.json) |
| 资料不足 | [input](../examples/runs/live/missing/input.json) | [result](../examples/runs/live/missing/result.json) |
| 工具保存失败 | [input](../examples/runs/live-retry-1/save_failure/input.json) | [result](../examples/runs/live-retry-1/save_failure/result.json) |
| 规则风险 | [input](../examples/runs/live/risk/input.json) | [result](../examples/runs/live/risk/result.json) |
| 时段冲突 | [input](../examples/runs/live-retry-1/conflict/input.json) | [result](../examples/runs/live-retry-1/conflict/result.json) |
| 重复提交 | [input](../examples/runs/live-retry-1/duplicate/input.json) | [首次](../examples/runs/live-retry-1/duplicate/first_run.json)、[重复](../examples/runs/live-retry-1/duplicate/result.json) |

## 首轮真实失败与修复

| 场景 | 实际问题 | 原始记录 |
|---|---|---|
| conflict | 模型响应未满足恰好1个工具调用，明确中止 | [Trace](../examples/runs/live/conflict/result.json) |
| save_failure | 尚未执行到保存工具就遇到模型协议错误，不能作为真实保存故障已通过 | [Trace](../examples/runs/live/save_failure/result.json) |
| duplicate | 第一次已有草稿，第二次模型协议错误，去重整体断言失败 | [第二次Trace](../examples/runs/live/duplicate/result.json) |
| changed_occupancy | 后一次成功建议20:00，但首次未成功，缺少可比对原草稿 | [首轮](../examples/runs/live/changed_occupancy/first_run.json)、[后一次](../examples/runs/live/changed_occupancy/result.json) |
| batch | M01成功；M06读取/补查后未重审，保存被阻断，最后行动依据格式/长度不合规 | [Trace](../examples/runs/live/batch/result.json) |

首轮代码的`MODEL_EXPECTED_ONE_TOOL_CALL`未记录数量，不能从旧记录确定是零调用还是多调用。修复后记录`diagnostics.tool_calls_count`，拒绝响应不执行动作，并向模型回传纠正反馈；每次纠正计入全局上限。非思考模式采用`required`，思考/自动模式保留`auto`。无效行动依据同样有界纠正；HTTP、非法JSON等仍明确停止。

工具反馈也补充“重新读取/补查会使旧审核失效，须重审”，并澄清可先保存待确认草稿。新增测试证明拒绝批次无执行、原调用ID完整回传、纠正不突破上限以及只重跑失败项。使用`--retry-failed`完成五项真实重跑，全部通过；该次没有触发协议纠正，拒绝/纠正分支仍主要由单元测试验证，不能据此保证今后绝不出现协议错误。

重跑批量记录还暴露结果展示问题：M01保存前审核通过，保存后模型再次读取使最终`review_status`显示为`unchecked`，但真实保存前的审核与提交回执均有效。随后结果投影改为保留成功保存时的审核快照，并输出`review_basis=at_successful_save`；新增`test_saved_review_snapshot_survives_observed_post_save_reread`复现该实际动作序列并通过。这个修改仅影响本地结果投影，未再次调用模型；原始重跑JSON仍保留原显示，不能冒充展示修正后的新实测输出。最新本地回归为55个测试通过，源码摘要见离线summary。

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

真实适配器单元测试使用伪造 HTTP 响应，验证了原 tool-call ID、tool observation 和思考字段内存回传，不是远端接口实测，不能当作真实模型成功记录。GitHub Actions 配置已随项目上传，云端执行状态以[仓库 Actions 页面](https://github.com/yangchong379/1-Agent/actions)为准；本地测试结果不等同于云端 CI 结果。

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

第一轮已完成并保留，后续优先运行失败项重跑，避免覆盖`examples/runs/live/`。核查normal、missing、risk、conflict、duplicate、save_failure的实际动作和反馈；模型可有不同顺序，不能仅靠结果文本一致判断正确。自动报告中的`real_model_decision_quality_verified=false`为默认边界标记，原文件不改写；AI逐项复核另存[review.json](../examples/runs/live/review.json)，并不代表生产级安全保证或候选人独立人工签字。后续实际结果须另行引用并说明源码版本与限制。

## 新增连续流量结果

[完整连续需求评估](08-product-traffic.md)：两天96条，离线业务目标完成22条、边界检查96条；当轮57个回归测试通过。历史真实结果保留，本轮真实流量结果见下节。

修复版通过 58 项单元测试和 24 条连续需求离线回放。单素材查询失败在当轮结束，返回 `query_failed` 和 `TOOL_UNAVAILABLE`。批次中的其余素材独立处理。复用修复前真实记录的请求与数据库快照时，007 的两项素材在 6 轮结束，019 的一项素材在 3 轮结束。两个用例的已有草稿与前置快照一致。修复后验证使用离线 Mock。[实际回归结果](../examples/regressions/query-failure.json)

## 2026-11-05真实运行

真实连续请求24条，业务目标完成9条，边界检查24/24；耗时2102.64秒。[原始报告](../examples/traffic/live-20261104-20261105-004121-535187/REPORT.md)、[Trace复核](../examples/traffic/live-20261104-20261105-004121-535187/REVIEW.md)、[文件及事实核查](../examples/traffic/live-20261104-20261105-004121-535187/review.json)。原始失败保留，不宣称单次通过率能代表生产可靠性。
