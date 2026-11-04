# Actual evaluation report

Mode: **offline_mock**

Mock results verify workflow and boundaries only; real model decisions remain unverified.

| Case | Expected | Actual | Checks |
|---|---|---|---|
| [normal](normal/result.json) | draft_ready | draft_ready | PASS |
| [conflict](conflict/result.json) | awaiting_confirmation | awaiting_confirmation | PASS |
| [missing](missing/result.json) | needs_info | needs_info | PASS |
| [risk](risk/result.json) | blocked | blocked | PASS |
| [save_failure](save_failure/result.json) | save_failed | save_failed | PASS |
| [duplicate](duplicate/result.json) | awaiting_confirmation | awaiting_confirmation | PASS |
| [supplement](supplement/result.json) | draft_ready | draft_ready | PASS |
| [confirmed](confirmed/result.json) | draft_ready | draft_ready | PASS |
| [changed_occupancy](changed_occupancy/result.json) | awaiting_confirmation | awaiting_confirmation | PASS |
| [no_slots](no_slots/result.json) | no_available_slot | no_available_slot | PASS |
| [step_limit](step_limit/result.json) | incomplete_step_limit | incomplete_step_limit | PASS |
| [batch](batch/result.json) | draft_ready | draft_ready | PASS |
| [privacy_copyright](privacy_copyright/result.json) | blocked | blocked | PASS |

Passed: 13/13

Source SHA-256: `3154db7619fda74d34a2adb90e1ba84e4b002e4bfe71919bc5d6cb349e1e9795`
