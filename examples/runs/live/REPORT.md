# Actual evaluation report

Mode: **live_model**

Live tool calls were used. Inspect actual traces before claiming model decision quality.

| Case | Expected | Actual | Checks |
|---|---|---|---|
| [normal](normal/result.json) | draft_ready | draft_ready | PASS |
| [conflict](conflict/result.json) | awaiting_confirmation | incomplete_model_error | FAIL |
| [missing](missing/result.json) | needs_info | needs_info | PASS |
| [risk](risk/result.json) | blocked | blocked | PASS |
| [save_failure](save_failure/result.json) | save_failed | incomplete_model_error | FAIL |
| [duplicate](duplicate/result.json) | awaiting_confirmation | incomplete_model_error | FAIL |
| [supplement](supplement/result.json) | draft_ready | draft_ready | PASS |
| [confirmed](confirmed/result.json) | draft_ready | draft_ready | PASS |
| [changed_occupancy](changed_occupancy/result.json) | awaiting_confirmation | awaiting_confirmation | FAIL |
| [no_slots](no_slots/result.json) | no_available_slot | no_available_slot | PASS |
| [step_limit](step_limit/result.json) | incomplete_step_limit | incomplete_step_limit | PASS |
| [batch](batch/result.json) | draft_ready | draft_ready | FAIL |
| [privacy_copyright](privacy_copyright/result.json) | blocked | blocked | PASS |

Passed: 8/13

Source SHA-256: `f3e78eae66b5c28c8272b1c437c018877e89e1db7ad244c3394f2965705c3f7d`
