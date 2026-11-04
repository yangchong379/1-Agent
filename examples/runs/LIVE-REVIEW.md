# 真实模型评估与修复后复核

首轮 **8/13** 通过；修复后只重跑失败项，结果 **5/5**。

[首轮原始报告](live/REPORT.md) · [首轮失败复核](live/REVIEW.md) · [重跑原始报告](live-retry-1/REPORT.md) · [逐项核查及文件摘要](live-comparison.json)

所有模型决策均来自真实 deepseek-flash 调用；业务资料、审核规则、时段工具为合成数据/本地实现。首轮失败与重跑原始文件均保留，没有改写失败结果。

**统计边界：下表组合了修复前后两个源码版本的案例证据，不是修复版本单次全量13/13，也不是稳定成功率。** 自动报告的默认质量验证标记保持不变，本复核由AI助手逐项检查，不代替候选人的独立人工签字。

| 场景 | 使用哪轮记录 | 实际状态 | 检查 | 输入 | 实际输出/Trace |
|---|---|---|---|---|---|
| normal | 首轮 | draft_ready | PASS | [input](live/normal/input.json) | [result](live/normal/result.json) |
| conflict | 修复后重跑 | awaiting_confirmation | PASS | [input](live-retry-1/conflict/input.json) | [result](live-retry-1/conflict/result.json) |
| missing | 首轮 | needs_info | PASS | [input](live/missing/input.json) | [result](live/missing/result.json) |
| risk | 首轮 | blocked | PASS | [input](live/risk/input.json) | [result](live/risk/result.json) |
| save_failure | 修复后重跑 | save_failed | PASS | [input](live-retry-1/save_failure/input.json) | [result](live-retry-1/save_failure/result.json) |
| duplicate | 修复后重跑 | awaiting_confirmation | PASS | [input](live-retry-1/duplicate/input.json) | [result](live-retry-1/duplicate/result.json) |
| supplement | 首轮 | draft_ready | PASS | [input](live/supplement/input.json) | [result](live/supplement/result.json) |
| confirmed | 首轮 | draft_ready | PASS | [input](live/confirmed/input.json) | [result](live/confirmed/result.json) |
| changed_occupancy | 修复后重跑 | awaiting_confirmation | PASS | [input](live-retry-1/changed_occupancy/input.json) | [result](live-retry-1/changed_occupancy/result.json) |
| no_slots | 首轮 | no_available_slot | PASS | [input](live/no_slots/input.json) | [result](live/no_slots/result.json) |
| step_limit | 首轮 | incomplete_step_limit | PASS | [input](live/step_limit/input.json) | [result](live/step_limit/result.json) |
| batch | 修复后重跑 | draft_ready, awaiting_confirmation | PASS | [input](live-retry-1/batch/input.json) | [result](live-retry-1/batch/result.json) |
| privacy_copyright | 首轮 | blocked | PASS | [input](live/privacy_copyright/input.json) | [result](live/privacy_copyright/result.json) |

## 关键决策核查

- 正常：审核通过、原时间可用后保存草稿并结束。
- 信息不足：补查为空、规则仍缺资料后停止，不保存。
- 规则风险：观察blocked后结束，禁止进入保存。
- 冲突：观察原时段占用后选可用替代，硬性要求保留、草稿待确认。
- 保存故障：工具返回SAVE_FAILED后由模型决定重试一次，再收到失败后结束；数据库零新增、输出明确失败。
- 重复/变更占用：对照首次和重复提交的草稿ID与数据库条数，检查没有新增第二份。
- 批量：检查两项分别获得无冲突草稿，替代硬性时间仍待确认。

## 修复内容与边界

非思考模式要求工具调用；零/多调用和不合规行动依据被拒绝，原调用获得未执行反馈，模型可在总步数上限内纠正。读取或补查后重审的要求通过工具反馈明确说明，且澄清可先保存待确认草稿。所有保存回执逐项与数据库快照核对，published保持false。

重跑batch原始结果中M01保存前审核通过，保存后再次读取使最终review_status显示unchecked。该原始显示没有改写；随后当前源码增加成功保存时的审核快照与review_basis，用实际动作序列做离线回归（55个测试通过）。此展示修正没有新增真实模型调用，因此当前源码摘要与重跑版本不同。

首轮源码摘要：`f3e78eae66b5c28c8272b1c437c018877e89e1db7ad244c3394f2965705c3f7d`。

重跑源码摘要：`f13df83ba03bb5e8cc6f375387370d69fca1ab3f243b84884b1d7b0c4bc05d67`。

包含后续结果展示修正的当前源码摘要：`3154db7619fda74d34a2adb90e1ba84e4b002e4bfe71919bc5d6cb349e1e9795`。

如需证明当前版本一次全量运行的表现，应另选新输出目录再次全量评估；本次为减少费用只重跑失败项。没有因此自动产生额外API调用。
