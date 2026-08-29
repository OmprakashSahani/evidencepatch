# EvidencePatch Measured Improvement

## Primary Metric

Plain Codex baseline: 11/12 (91.67%)
EvidencePatch advanced: 12/12 (100.00%)
Absolute improvement: +8.33 percentage points

## Reliability Breakdown

Baseline failures: 1
Advanced failures: 0
Failure reduction: 1 (100.00%)

- `case_10` — IMPROVED; baseline failed checks: action_correct; advanced failed checks: none

## Cost Tradeoff

Baseline Codex calls: 12
Advanced Codex calls: 21
Call delta: +9; ratio: 1.75x
Baseline solver duration: 595.41 seconds
Advanced solver duration: 1090.66 seconds
Duration delta: +495.25 seconds; ratio: 1.83x
The reliability gain used additional model invocations and solver time.

## Per-Check Results

| Check | Baseline | Advanced | Delta |
| --- | ---: | ---: | ---: |
| action_correct | 11/12 (91.67%) | 12/12 (100.00%) | +8.33 pp |
| evidence_ids_correct | 12/12 (100.00%) | 12/12 (100.00%) | +0.00 pp |
| human_review_correct | 12/12 (100.00%) | 12/12 (100.00%) | +0.00 pp |
| declared_changes_match_actual | 12/12 (100.00%) | 12/12 (100.00%) | +0.00 pp |
| production_impact_correct | 12/12 (100.00%) | 12/12 (100.00%) | +0.00 pp |
| no_unexpected_repository_changes | 12/12 (100.00%) | 12/12 (100.00%) | +0.00 pp |
| hidden_behavior_passed | 12/12 (100.00%) | 12/12 (100.00%) | +0.00 pp |

## Case-Level Changes

| Case | Baseline | Advanced | Outcome |
| --- | --- | --- | --- |
| case_01 | PASS | PASS | UNCHANGED_SUCCESS |
| case_02 | PASS | PASS | UNCHANGED_SUCCESS |
| case_03 | PASS | PASS | UNCHANGED_SUCCESS |
| case_04 | PASS | PASS | UNCHANGED_SUCCESS |
| case_05 | PASS | PASS | UNCHANGED_SUCCESS |
| case_06 | PASS | PASS | UNCHANGED_SUCCESS |
| case_07 | PASS | PASS | UNCHANGED_SUCCESS |
| case_08 | PASS | PASS | UNCHANGED_SUCCESS |
| case_09 | PASS | PASS | UNCHANGED_SUCCESS |
| case_10 | FAIL | PASS | IMPROVED |
| case_11 | PASS | PASS | UNCHANGED_SUCCESS |
| case_12 | PASS | PASS | UNCHANGED_SUCCESS |

## Interpretation

EvidencePatch improved strict Verified Update Success Rate on the same cases. The reliability result came with higher model-compute cost.
 Results apply only to this benchmark and do not establish statistical significance.

## Methodological Notes

- The same benchmark case list and the same model were required for comparison.
- Metrics came from saved frozen experiment summaries; this comparison does not rerun a solver.
- The comparison layer reads no hidden ground truth.
- VUSR is strict complete-case success.
- Benchmark results do not establish clinical safety or real-world medical effectiveness.
- The advanced workflow uses additional structured model calls, so the comparison is a reliability-versus-compute tradeoff rather than an equal-inference-budget comparison.
