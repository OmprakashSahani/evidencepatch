# EvidencePatch Submission

## Project Name

EvidencePatch

## One-Line Description

Fresh medical evidence is not automatically actionable medical evidence; EvidencePatch is an MCP-native evidence-to-code verification boundary for clinical-software maintenance.

## Intended User

Clinical-informatics engineers and healthcare-software teams maintaining executable medication-safety and clinical decision-support rules.

## Problem

The bottleneck is not only writing code. Teams must determine which evidence controls current behavior, distinguish recency from authority, handle credible weaker conflict, authorize only supported executable changes, and prove that the repository matches the declared result. Combining all of those decisions inside one generative step makes consequential maintenance difficult to audit.

## What We Built

- Codex extraction of a structured Clinical Change Contract
- Deterministic `PATCH` / `NO_PATCH` / `ESCALATE` governance
- A separately authorized Codex patch stage used only after `PATCH`
- Repository-impact analysis and declared-change verification
- Deterministic result-provenance verification
- A synthetic benchmark with hidden behavior evaluation
- An EvidencePatch MCP server exposing three governance/verification tools
- Exa MCP integration for public evidence discovery and fetching
- Explicit human-review boundaries for `PATCH` and `ESCALATE`

## Agent Stack

- Coding/reasoning agent: OpenAI Codex CLI
- Official benchmark model: `gpt-5.6-sol`
- Public evidence discovery: Exa MCP
- Deterministic governance and verification: EvidencePatch MCP
- Official retry policy: none

Codex handles semantic interpretation and authorized implementation. EvidencePatch MCP is deterministic infrastructure, not a generative coding agent.

## End-to-End Flow

```text
Exa MCP
→ host/agent
→ Clinical Change Contract
→ EvidencePatch deterministic governance
→ optional separately authorized Codex PATCH stage
→ repository/provenance verification
→ human review
```

## Measured Improvement

Both workflows used `gpt-5.6-sol` on the same 12 synthetic cases.

| Measure | Plain Codex | EvidencePatch | Delta |
| --- | ---: | ---: | ---: |
| Verified cases | 11/12 | 12/12 | verified failures 1 → 0 |
| VUSR | 91.67% | 100.00% | +8.33 percentage points |
| Codex calls | 12 | 21 | 1.75× |
| Solver duration | 595.405 s | 1090.656 s | 1.83× |

This is a reliability-versus-compute result, not an equal-inference-budget comparison. No statistical-significance claim is made.

## Main Failure Mode

The baseline's only complete-case failure was `action_correct`. The permitted public final-rescore artifact does not retain the submitted baseline action, so it is not reconstructed.

## Most Important Change

The Clinical Change Contract plus deterministic disposition governance separated evidence interpretation from final action authorization. It addressed the only complete-case baseline failure observed in the final comparison, although this benchmark alone does not prove causality.

## Removed Experiment / Design

The direct one-shot baseline allowed the model to choose the final maintenance disposition. Model-controlled final disposition was not retained: Codex now proposes the contract, and deterministic governance selects the action.

## Public MCP Demonstration

The public demo used an FDA metformin/eGFR source and a published AJKD observational study. The corrected contract represented the FDA source as `AUTHORITATIVE/CURRENT` and the study as `NON_AUTHORITATIVE/CURRENT`. The study created conflicting change pressure, while the synthetic repository matched controlling authority. EvidencePatch returned `ESCALATE`, required human review, found the repositories clean, and passed 5/5 provenance checks.

The host initially marked the published paper `PROVISIONAL`; a human corrected it to `CURRENT`. No Exa re-search or repository change occurred during correction. The action remained `ESCALATE`. This is software-maintenance evidence, not medical advice.

## Reproducibility

- 685 passing project regression tests with `PYTHONPATH=. pytest tests -q`
- Cases 01–12 validated separately
- Official tag: `evidencepatch-advanced-official-v1`
- Official source commit: `ff000f41d01ba7a351fdcc7a082e3fc046294941`
- Contract extraction prompt SHA-256: `a6fdef8e656f415acca5f21d3f79e567afc4112af1d86e98e5fe16302a8d0cd0`
- Authorized patch prompt SHA-256: `0c7d2a3a0497de8af86d6d2fccea67a9d9037e0ecc1a88c93ecbd21aaf620e08`
- No official benchmark retries
- Byte-identical public artifact snapshots with recorded hashes
- Representative agent trajectories and an under-five-minute script requiring a real MCP execution

Historical monetary API cost was not recorded in the frozen official artifacts. The submission reports calls and solver duration rather than inventing a dollar estimate.

## Safety / Limitations

- The benchmark contains 12 synthetic cases and one measured model.
- The result is not a statistical-significance or clinical-safety claim.
- EvidencePatch does not auto-deploy software.
- `PATCH` and `ESCALATE` require human review.
- Consequential changes remain sandboxed.
- The public demonstration is not treatment advice.

## Key Insight / Hot Take

In consequential software maintenance, “no code change” is not a complete outcome category. Some evidence states require explicit escalation, and the boundary between `PATCH`, `NO_PATCH`, and `ESCALATE` should be governed separately from code generation.

## Key Links

- [README](../README.md)
- [Improvement Changelog](../CHANGELOG.md)
- [Architecture](architecture.md)
- [Evaluation](evaluation.md)
- [Reproducibility](reproducibility.md)
- [Representative trajectories](trajectories.md)
- [Public MCP demo](public_mcp_demo.md)
- [Under-five-minute demo script](demo_script.md)
- [Final submission audit](final_audit.md)
- [Official artifact manifest](../artifacts/official/README.md)
- [Official comparison](../artifacts/official/comparison.md)
