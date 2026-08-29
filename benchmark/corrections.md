# Benchmark Corrections

## 2026-08-29 — Case 12 human-review label

- Previous hidden value: `requires_human_review = true`
- Corrected value: `requires_human_review = false`

Reason: Case 12's public task and authoritative evidence require human review before deployment for an actual software change. The correct action is `NO_PATCH` because the revision is behaviorally equivalent, so no software change is being deployed.

Discovery: The inconsistency was discovered only after the frozen plain-Codex baseline run during failure analysis.

Fairness:

- No Codex case was rerun.
- No solver output was changed.
- `BASELINE_PROMPT` was not changed.
- No evaluator scoring logic was changed.
- The same frozen solver output will be rescored.
- The previous 10/12 score is superseded because one failure was caused by an inconsistent benchmark label.

Case 10 remains unchanged and remains a genuine baseline action-selection failure.
