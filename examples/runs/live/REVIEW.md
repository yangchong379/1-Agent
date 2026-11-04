# 首轮真实模型评估复核

模型：deepseek-flash。首轮13组，8/13通过，5组失败。原始summary/result/Trace保持不变。

运行源码摘要：`f3e78eae66b5c28c8272b1c437c018877e89e1db7ad244c3394f2965705c3f7d`。首轮对应修复前版本，不能当成修复后代码的实测结果。

| 场景 | 首轮结果 | 记录 |
|---|---|---|
| normal | PASS | [实际输出与Trace](normal/result.json) |
| conflict | FAIL | [实际输出与Trace](conflict/result.json) |
| missing | PASS | [实际输出与Trace](missing/result.json) |
| risk | PASS | [实际输出与Trace](risk/result.json) |
| save_failure | FAIL | [实际输出与Trace](save_failure/result.json) |
| duplicate | FAIL | [实际输出与Trace](duplicate/result.json) |
| supplement | PASS | [实际输出与Trace](supplement/result.json) |
| confirmed | PASS | [实际输出与Trace](confirmed/result.json) |
| changed_occupancy | FAIL | [实际输出与Trace](changed_occupancy/result.json) |
| no_slots | PASS | [实际输出与Trace](no_slots/result.json) |
| step_limit | PASS | [实际输出与Trace](step_limit/result.json) |
| batch | FAIL | [实际输出与Trace](batch/result.json) |
| privacy_copyright | PASS | [实际输出与Trace](privacy_copyright/result.json) |

## 失败原因与修复边界

- conflict、save_failure、duplicate：MODEL_EXPECTED_ONE_TOOL_CALL。初版没有记录调用数量，无法从旧日志断言是零调用还是多调用；能确定模型响应未满足恰好一次调用的契约。
- changed_occupancy：最终正确保存20:00待确认草稿，但首次提交失败，未形成可供重复核对的原草稿，因此去重断言未通过。
- batch：M01成功保存，M06反复读取/补查后未重新审核，保存被REVIEW_REQUIRED阻断；最终因MODEL_INVALID_RATIONALE结束。此错误表示依据不满足类型或长度限制，原始违规内容未保存。只保存一份草稿，明确返回部分未完成，没有虚报全部成功。

修复：非思考模式要求工具调用；将零/多调用及无效依据显式反馈模型，拒绝响应不执行动作，纠正计入全局步数上限；工具明确指出读取/补查后须重审，并说明可先保存待确认草稿。代码回归测试通过不等于修复后真实模型效果已验证。

## 已观察的动态路径

- [正常](normal/result.json)：读取→审核通过→查询→保存17:00草稿→结束。
- [资料不足](missing/result.json)：读取→补查为空→审核needs_info→停止，不查询或保存。
- [规则风险](risk/result.json)：读取→审核blocked→停止，不保存。
- [补查成功](supplement/result.json)：读取→补查到版权→审核通过→查询→保存。
- [用户明确批准](confirmed/result.json)：观察已有待确认草稿及精确批准19:00→保存UPDATED/confirmed，ID不变。

至少两种不同工具结果下的真实模型决策路径已有记录；仍不能声称全部真实验收通过。

## 数据与安全核查

AI逐项核对了13组最终状态、工具观察和数据库快照：所有场景保持published=false；保存成功声明与快照一致；硬性要求的替代草稿保持pending_user或具有精确用户批准。业务断言失败与这些安全边界的通过分别记录于[review.json](review.json)。这不是生产安全保证，也不是独立人工签字。

下一步在本机运行 `py -3.11 scripts/connect_deepseek.py --retry-failed`，只补跑5个失败项，保存到独立的live-retry-N目录。保留首轮失败记录并比较源码摘要和新Trace。
