# Evaluation

## Benchmark and metric

The official experiment used `gpt-5.6-sol` on the same 12 synthetic medication-safety and clinical-software maintenance cases for both workflows. The plain Codex configuration is the baseline; the advanced configuration adds structured contract extraction, deterministic governance, and a separate authorized patch call when governance returns `PATCH`.

The primary metric is Verified Update Success Rate (VUSR). A case succeeds only when every check passes:

1. `action_correct`
2. `evidence_ids_correct`
3. `human_review_correct`
4. `declared_changes_match_actual`
5. `production_impact_correct`
6. `no_unexpected_repository_changes`
7. `hidden_behavior_passed`

## Official results

| Measure | Plain Codex | EvidencePatch advanced | Delta |
| --- | ---: | ---: | ---: |
| Verified cases | 11/12 | 12/12 | failures 1 → 0 |
| VUSR | 91.67% | 100.00% | +8.33 percentage points |
| Codex calls | 12 | 21 | 1.75× |
| Solver duration | 595.405 s | 1090.656 s | 1.83× |

For the advanced run, every one of the seven checks passed in all 12 cases. For the baseline, six checks passed in all 12 cases; `action_correct` passed in 11/12. The only complete-case transition was `case_10`, FAIL → PASS, and its baseline failure was only `action_correct`.

This is a reliability-versus-compute tradeoff, not a free improvement or an equal-inference-budget comparison. The 12-case result is descriptive for this synthetic benchmark; it is not presented as statistically significant and does not establish clinical safety.

## Frozen provenance

- Official benchmark source commit: `ff000f41d01ba7a351fdcc7a082e3fc046294941`
- Official tag: `evidencepatch-advanced-official-v1`
- Contract extraction prompt SHA-256: `a6fdef8e656f415acca5f21d3f79e567afc4112af1d86e98e5fe16302a8d0cd0`
- Authorized patch prompt SHA-256: `0c7d2a3a0497de8af86d6d2fccea67a9d9037e0ecc1a88c93ecbd21aaf620e08`
- Retry policy: none
- Advanced official run: no workflow failures, no timeouts, and no nonzero exits

The official tag pins the benchmark implementation. Later reporting and MCP product work were added on `main` without changing that frozen implementation.

## Methodological disclosures

### Evaluator infrastructure correction

An early hidden-behavior evaluation attempt incorrectly invoked pytest through the project Python interpreter, where pytest was unavailable. The evaluator was corrected to use the available pytest executable. The same frozen solver workspaces were rescored, and no solver rerun was performed because of the infrastructure issue. The invalid infrastructure-zero score is not treated as a model result.

### Case 12 benchmark-validity correction

After baseline failure analysis, Case 12's human-review ground-truth flag was corrected from true to false because the public task requires human review for actual software changes, while the case is semantic equivalence with no software change. The already-generated solver output was rescored; there was no solver retry or semantic rerun. This was a benchmark-label correction, not model tuning.

## Limitations

- The benchmark has 12 synthetic cases and does not represent clinical deployment validation.
- The comparison does not use equal inference budgets: advanced extraction occurs for every case, with a separate patch call only when authorized.
- One model and one frozen case set were measured.
- Complete-case VUSR is intentionally strict but cannot cover every real-world failure mode.
- Hidden behavior checks protect evaluation integrity; public summaries do not disclose private answers beyond their saved aggregate and per-check reporting.
- No statistical-significance claim is made.

## Official artifacts

- [Baseline benchmark summary](../artifacts/official/baseline_benchmark_summary.json)
- [Advanced benchmark summary](../artifacts/official/advanced_benchmark_summary.json)
- [Advanced run provenance](../artifacts/official/advanced_run_provenance.json)
- [Deterministic comparison JSON](../artifacts/official/comparison.json)
- [Deterministic comparison report](../artifacts/official/comparison.md)
- [Artifact manifest](../artifacts/official/README.md)
