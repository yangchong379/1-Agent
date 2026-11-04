# 01 需求与成功标准

## 用户、问题和范围

用户是内容运营人员，需要批量知道素材是否能进入排期、资料缺什么、风险在哪里、期望时段是否可用、草稿是否真正保存。业务目标是减少漏审、冲突与重复草稿，并把“推荐时间”与“用户已同意的时间”明确区分。

本次选择题目 1，交付 Python CLI。输入为素材 ID、渠道、含时区的期望时间、是否硬性要求、用户已批准的精确时段；元数据、规则、已有排期由合成数据和本地工具提供。输出为逐项结果及可核查的执行轨迹。只写草稿，无发布工具。

非目标：界面、线上部署、多 Agent、Agent 框架、生产 Runtime、真实媒体识别和真实平台集成。本项目没有使用多 Agent 或外部业务数据。

## 验收标准与材料映射

| 必验收点 | 成功标准 | 输入 | 实际结果及 Trace |
|---|---|---|---|
| 正常排期 | 审核通过、精确要求时段可用、确认草稿保存 | [normal](../examples/inputs/normal.json) | [normal/result.json](../examples/runs/mock/normal/result.json) |
| 信息缺失 | 补查后仍缺资料则列出缺失项，不保存 | [missing](../examples/inputs/missing.json) | [missing/result.json](../examples/runs/mock/missing/result.json) |
| 规则风险 | 禁用表述、版权/隐私风险明确阻断 | [risk](../examples/inputs/risk.json) | [risk](../examples/runs/mock/risk/result.json)、[版权/隐私](../examples/runs/mock/privacy_copyright/result.json) |
| 时段冲突 | 更换可用时间并保留硬性要求，等待确认 | [conflict](../examples/inputs/conflict.json) | [conflict/result.json](../examples/runs/mock/conflict/result.json) |
| 重复提交 | 同一/不同请求 ID 的相同业务只保留一个草稿 | [duplicate](../examples/inputs/duplicate.json) | [first_run](../examples/runs/mock/duplicate/first_run.json)、[第二次](../examples/runs/mock/duplicate/result.json)、[数据库快照](../examples/runs/mock/duplicate/database_snapshot.json) |
| 保存失败 | 写入事务回滚，明确失败，不能返回成功 ID | [save_failure](../examples/inputs/save_failure.json) | [save_failure/result.json](../examples/runs/mock/save_failure/result.json)、[零草稿快照](../examples/runs/mock/save_failure/database_snapshot.json) |

补充标准：补查成功可继续排期；占用时段变化后建议发生变化；精确同意可更新原草稿；多素材互不冲突；时段耗尽能结束；达到全请求上限返回明确未完成；未知素材不能排期；恶意或不合规模型动作不能绕过工具约束。

## 不可越过的边界

1. 原始期望时间和硬性要求始终保留在结果里，模型无工具可更改请求。
2. 模型工具没有确认权限参数；精确用户批准来自 CLI 输入，不能从素材描述推导。
3. `published` 恒为 false；`saved` 仅根据数据库提交后的工具回执得出。
4. 模型调用次数与工具调用次数均受 `--max-steps` 限制，范围 1–100，默认 40，覆盖整个批量请求。
5. 离线 Mock 是可复现的流程替身，不能证明真实 LLM 选择动作的能力；真实模型 Trace 是待补材料。

## 关键业务取舍

采用半开区间 `[start,end)` 检测冲突，因此 18:00–19:00 与 19:00–20:00 不冲突。待确认草稿也占用建议时段，避免团队同时收到相同时间的两个草稿。每素材/渠道唯一活动草稿使重复提交可跨进程去重；变更已有草稿的原要求会返回待处理冲突，本版本不自动覆盖。
