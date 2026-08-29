# Experiment Changelog

This changelog records experimental and product milestones. It is not a release-marketing log, and the iterations were not selected using hidden benchmark answers.

## Iteration 2B — Public documentation and frozen evidence packaging

- Added public architecture, evaluation, reproducibility, and MCP demo documentation.
- Copied five byte-identical public snapshots from historical saved runs into `artifacts/official/`.
- Documented the measured improvement: VUSR 91.67% (11/12) to 100.00% (12/12), a gain of 8.33 percentage points, with verified failures decreasing from one to zero.
- Made the reliability-versus-compute tradeoff explicit: calls increased from 12 to 21 (1.75×) and solver duration from 595.405 to 1090.656 seconds (1.83×).

## Product MCP surface and public evidence demo

- Added the deterministic EvidencePatch MCP surface: contract assessment, repository-impact analysis, and result-provenance verification.
- Ran an Exa-backed public evidence demo using an FDA metformin rule and a published AJKD observational study.
- Recorded the human correction of the AJKD paper's publication lifecycle status from `PROVISIONAL` to `CURRENT`; its authority remained `NON_AUTHORITATIVE`.
- Re-submitted the corrected contract only to deterministic EvidencePatch tools. The action remained `ESCALATE`, no repository content changed, and all five provenance checks passed.

## Advanced workflow and official result

- Added the Clinical Change Contract and frozen deterministic governance gate.
- Added contract extraction and its protected runner.
- Added the separate authorized patch runner.
- Integrated the advanced workflow and advanced benchmark harness.
- Recorded the official 12/12 advanced result with `gpt-5.6-sol`.
- Added deterministic comparison reporting against the plain Codex baseline.
- Tagged the frozen benchmark implementation as `evidencepatch-advanced-official-v1` at source commit `ff000f41d01ba7a351fdcc7a082e3fc046294941`.

## Plain Codex baseline

- Added a fair plain Codex baseline on the same 12 cases and model.
- Recorded 11/12 verified case success (91.67% VUSR), 12 calls, and 595.405 seconds of solver duration.
- The only complete-case transition in the later comparison was `case_10`, from FAIL to PASS; the baseline failed only `action_correct` for that case.

## Benchmark and evaluator foundation

- Added the 12-case synthetic medication-safety and clinical-software maintenance benchmark.
- Added static declaration/provenance checks and hidden behavior evaluation.
- Defined strict complete-case Verified Update Success Rate: all seven checks must pass.

### Evaluator infrastructure correction

An early hidden-behavior evaluation attempt invoked pytest through the project Python interpreter, where pytest was unavailable. The evaluator was corrected to use the available pytest executable, and the same frozen solver workspaces were rescored. No solver rerun occurred. The invalid infrastructure-zero score is not a model result.

### Case 12 benchmark-label correction

After baseline failure analysis, Case 12's human-review ground-truth flag was corrected from true to false. The public task requires human review for actual software changes, while Case 12 is semantic equivalence with no software change. The already-generated solver output was rescored with no solver retry or semantic rerun. This was a benchmark-label correction, not model tuning.
