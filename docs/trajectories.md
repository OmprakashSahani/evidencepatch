# Representative Agent Trajectories

These are representative frozen traces for auditability, not additional benchmark attempts. No solver was rerun to create this document.

## Agent Inventory

1. Plain Codex baseline solver — one OpenAI Codex CLI solve that interpreted the public case and produced the proposed result.
2. Codex Clinical Change Contract extraction agent — converted public task, evidence, and repository state into a structured contract.
3. Authorized Codex patch agent — implemented changes only after deterministic governance returned `PATCH`.
4. Host/agent in the public MCP demo — orchestrated public retrieval, proposed the contract, and submitted it for deterministic assessment and verification.

Exa MCP is the evidence-discovery tool/provider, not the final governance agent. EvidencePatch MCP is deterministic governance and verification, not a generative coding agent. The traces below show prompt identity or instructions, externally observable actions/responses, and result; they do not reproduce private chain-of-thought.

## Trajectory A — Plain Codex baseline failure mode

### Instructions / prompt identity

- System/workflow: plain Codex direct one-shot baseline
- Model: `gpt-5.6-sol`
- Solver calls: 1
- Retries: none
- Input boundary: public task, evidence, repository, and result schema
- Baseline prompt SHA-256: `75d55642223087f296b466094c3c68566ff2056c9fa956ec80f76ab45451c364`

### Observable action / response

- Public evaluation outcome: `verified_success = false`
- Public failed checks: `action_correct` only

The allowed final-rescore directory contains only its aggregate `benchmark_summary.json`. That public snapshot does not retain case_10's submitted action or a case-level result artifact, so the actual baseline action is intentionally not reconstructed or inferred here.

The observable failure mode is narrower than a claim about medical reasoning: the direct one-shot solver selected an incorrect software-maintenance disposition according to `action_correct`. The permitted public final-rescore artifacts do not retain the submitted action, so this document does not reconstruct the exact wrong disposition. The allowed public record does not establish that the model misunderstood the medical evidence.

### Result

The public complete-case result was FAIL on `action_correct` only. No retry or human feedback occurred during the benchmark run.

### Evidence Trail

- `runs/plain_codex_baseline_gpt56sol_20260829_final_rescore/benchmark_summary.json`
- `artifacts/official/baseline_benchmark_summary.json`
- `artifacts/official/comparison.json`
- `artifacts/official/comparison.md`

## Trajectory B — EvidencePatch advanced recovery

### Instructions / prompt identity

- Model: `gpt-5.6-sol`
- Contract extraction calls: 1
- Patch calls: 0
- Total Codex calls: 1
- Retries: none
- Contract extraction prompt SHA-256: `a6fdef8e656f415acca5f21d3f79e567afc4112af1d86e98e5fe16302a8d0cd0`

### Observable actions / workflow responses

- Extraction return code: 0
- Extraction timeout: false
- Workflow completed successfully: true

### Sequence

```text
public inputs
→ contract extraction
→ Clinical Change Contract
→ deterministic governance
→ ESCALATE
→ no patch stage
→ deterministic result
```

The material contract fields were:

```json
{
  "evidence": [
    {
      "authority": "AUTHORITATIVE",
      "status": "CURRENT",
      "proposes_executable_change": false,
      "conflicts_with_current_authority": false
    },
    {
      "authority": "NON_AUTHORITATIVE",
      "status": "UNKNOWN",
      "proposes_executable_change": true,
      "conflicts_with_current_authority": true
    }
  ],
  "executable_behavior_change": false,
  "semantic_equivalence": true,
  "unresolved_conflict": false,
  "ambiguous_or_incomplete": false
}
```

This made the distinction explicit: the repository was equivalent to controlling current authority, while weaker evidence still created incompatible change pressure. Frozen deterministic governance returned `ESCALATE`, required human review, declared no changed files, and did not authorize a patch-stage call.

The official public summary records `verified_success = true` and `failed_checks = []`. The benchmark solver received no hidden evaluator feedback, and there was no retry.

### Result

`ESCALATE`, human review required, no patch stage, and verified success with no failed checks.

### Evidence Trail

- `runs/evidencepatch_advanced_gpt56sol_20260829/experiment_metadata.json`
- `runs/evidencepatch_advanced_gpt56sol_20260829/case_10/extraction_codex/run_metadata.json`
- `runs/evidencepatch_advanced_gpt56sol_20260829/case_10/workspace/evidencepatch_contract.json`
- `runs/evidencepatch_advanced_gpt56sol_20260829/case_10/workflow.json`
- `runs/evidencepatch_advanced_gpt56sol_20260829/case_10/workspace/evidencepatch_result.json`
- `runs/evidencepatch_advanced_gpt56sol_20260829/benchmark_summary.json`
- `artifacts/official/advanced_benchmark_summary.json`

## Trajectory C — Full authorized PATCH path

The representative successful PATCH trace is advanced `case_01`. It demonstrates that EvidencePatch is not merely an escalation classifier.

### Instructions / prompt identity

- Model: `gpt-5.6-sol`
- Contract extraction calls: 1
- Patch calls: 1
- Total Codex calls: 2
- Retries: none
- Contract extraction prompt SHA-256: `a6fdef8e656f415acca5f21d3f79e567afc4112af1d86e98e5fe16302a8d0cd0`
- Authorized patch prompt SHA-256: `0c7d2a3a0497de8af86d6d2fccea67a9d9037e0ecc1a88c93ecbd21aaf620e08`

### Observable actions / workflow responses

- Both Codex calls returned 0 and did not time out

### Sequence

```text
public inputs
→ contract extraction
→ deterministic PATCH authorization
→ separate authorized Codex patch call
→ repository diff
→ deterministic result
→ verified success
```

The contract recorded one `AUTHORITATIVE`, `CURRENT` evidence item that proposed executable change, with `executable_behavior_change = true`, `semantic_equivalence = false`, and neither unresolved conflict nor ambiguity. Deterministic governance authorized `PATCH` before implementation began.

The separate patch stage produced the observable declared diff:

```json
{
  "action": "PATCH",
  "changed_files": [
    "medication_rules/velunex.py",
    "tests/test_velunex.py"
  ],
  "human_review_required": true
}
```

The workflow completed successfully. The official summary records `verified_success = true` and `failed_checks = []`. No hidden behavior-test implementation is reproduced here.

### Result

`PATCH`, two declared changed files, human review required, and verified success with no failed checks.

### Evidence Trail

- `runs/evidencepatch_advanced_gpt56sol_20260829/experiment_metadata.json`
- `runs/evidencepatch_advanced_gpt56sol_20260829/case_01/extraction_codex/run_metadata.json`
- `runs/evidencepatch_advanced_gpt56sol_20260829/case_01/patch_codex/run_metadata.json`
- `runs/evidencepatch_advanced_gpt56sol_20260829/case_01/workspace/evidencepatch_contract.json`
- `runs/evidencepatch_advanced_gpt56sol_20260829/case_01/workflow.json`
- `runs/evidencepatch_advanced_gpt56sol_20260829/case_01/workspace/evidencepatch_result.json`
- `runs/evidencepatch_advanced_gpt56sol_20260829/benchmark_summary.json`
- `artifacts/official/advanced_benchmark_summary.json`

## Human Review Checkpoint: Public MCP Demo

```text
Exa discovery/fetch
→ host structured interpretation
→ EvidencePatch assess_change_contract
→ repository impact
→ provenance verification
→ human notices paper lifecycle classification issue
→ PROVISIONAL corrected to CURRENT
→ same deterministic tools re-run
→ action remains ESCALATE
→ 5/5 provenance checks pass
```

The responsibilities remained distinct. Exa discovered the public evidence. The host proposed the Clinical Change Contract. A human corrected the host's interpretation of the published paper's lifecycle status. EvidencePatch deterministically governed and verified the corrected proposition.

Exa discovery and fetch occurred in the original public run. EvidencePatch responded through `assess_change_contract`, `analyze_repository_impact`, and `verify_result_provenance`. There was no Exa re-search during the correction, no repository modification, and no benchmark involvement. The same three deterministic EvidencePatch tools reran after the human corrected `PROVISIONAL` to `CURRENT`; the action remained `ESCALATE` and 5/5 provenance checks passed. This is the explicit human-feedback example: review changed a structured interpretation without silently changing software, and the deterministic disposition remained stable.

Evidence trail: `docs/public_mcp_demo.md`.

## Trajectory Summary

| Trace | Model calls | Patch call | Retry | Human feedback during run | Outcome |
| --- | ---: | --- | --- | --- | --- |
| Plain baseline case_10 | 1 | No | None | No | FAIL; `action_correct` only |
| Advanced case_10 | 1 | No | None | No | `ESCALATE`; verified success |
| Advanced PATCH example (case_01) | 2 | Yes, separately authorized | None | No | `PATCH`; verified success |
| Public MCP human-review demo | N/A — not benchmark Codex model calls | No software patch | N/A | Yes, explicit correction | `ESCALATE`; 5/5 provenance checks passed |

## What the Trajectories Show

- Direct code-generation ability was already strong on most cases: the baseline achieved 11/12 complete-case success.
- The measured gain came from explicit evidence and governance structure correcting a disposition failure, not from repeated attempts.
- EvidencePatch separates proposed evidence interpretation from deterministic action authorization.
- `PATCH` uses a separately authorized implementation stage after governance.
- Retries were not used to obtain the official score.
- Human review remains a real checkpoint: it can correct a proposed contract and require deterministic reassessment rather than being simulated away.

These observations are limited to the frozen 12-case synthetic benchmark and the documented public demo. They are not a statistical-significance or clinical-safety claim.
