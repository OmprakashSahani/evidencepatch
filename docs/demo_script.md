# EvidencePatch Demo Script

Target runtime: **approximately 4:30–4:50**. Hard maximum: **under 5:00**.

The video must show one real terminal/MCP product execution from public evidence retrieval through final provenance verification. Documentation alone is not a substitute. Do not run the expensive 12-case benchmark live.

## 0:00–0:25 — Problem and intended user

**Show:** the top of `README.md`.

**Say:**

“Clinical-informatics engineers and healthcare-software teams translate changing evidence into executable medication-safety rules. Fresh evidence is not automatically actionable evidence: a new study can matter without superseding the source that controls current software behavior. EvidencePatch governs this evidence-to-code boundary; it does not make clinical decisions.”

## 0:25–0:55 — Agent stack and architecture

**Show:** `README.md` Agent Stack and architecture diagram.

**Say:**

“OpenAI Codex CLI with `gpt-5.6-sol` performs semantic contract extraction and, only when authorized, implementation. Exa MCP discovers public evidence. EvidencePatch MCP provides deterministic governance and repository/provenance verification. Codex proposes; deterministic rules authorize. The official benchmark used no retries.”

## 0:55–1:30 — Measured result and compute tradeoff

**Show:** `artifacts/official/comparison.md`.

**Say exactly:**

“On the same 12 synthetic cases and same model, plain Codex scored 11 out of 12, or 91.67% VUSR. EvidencePatch scored 12 out of 12, or 100%. That is plus 8.33 percentage points, with verified failures falling from one to zero.”

Immediately disclose:

“Calls increased from 12 to 21, or 1.75 times. Solver duration increased from 595.405 to 1090.656 seconds, or 1.83 times. This is a reliability-versus-compute tradeoff, not an equal-budget, statistical-significance, or clinical-safety claim.”

## 1:30–2:00 — Main failure mode and removed experiment

**Show:** `docs/trajectories.md`, then briefly `CHANGELOG.md`.

**Say:**

“The direct one-shot baseline let the model choose the final disposition. Its only complete-case failure was `action_correct`; the public artifact does not retain the submitted action, so we do not reconstruct it. After observing that failure, the final workflow removed final disposition selection from the generative solver and moved it into deterministic governance.

“The most important architectural change was the Clinical Change Contract plus deterministic disposition governance. It addressed the only complete-case baseline failure observed in this benchmark, although this comparison alone is not causal proof. The Improvement Changelog records that decision, the authorized patch stage, methodological corrections, and the added compute cost.”

## 2:00–3:30 — Real terminal/MCP execution

**Show:** a configured Codex terminal. Paste the recording-time prompt below and show actual tool calls and responses. Keep the terminal focused on the returned fields.

The live path is a short rerun of the reviewed public metformin/eGFR product example, not a benchmark case. It must operate outside `benchmark/`, use `/tmp`, leave candidate byte-identical to canonical, and make no production software change.

**Narrate while it runs:**

“Exa is retrieving the two established public sources: the FDA document and the published AJKD article. The host checks the fetched evidence and proposes the corrected structured interpretation. EvidencePatch then assesses the contract, compares canonical and candidate repositories, and verifies the declared result. These are real tool responses; if they differ from the historical demo, we report the live result exactly.”

Show, as returned:

- governance action;
- `human_review_required`;
- clean or changed repository impact;
- each provenance check and overall verification result.

### Copy/paste recording-time prompt

```text
Run one controlled public-evidence EvidencePatch product demonstration for video recording.

This is not a benchmark. Do not access benchmark/, hidden/, ground_truth.json, saved runs, saved comparison artifacts, or evaluator inputs. Do not invoke benchmark or evaluator workflows. Do not modify any tracked repository file. Do not deploy anything and do not provide patient-specific advice.

Use Exa MCP only to retrieve/fetch these already-established public sources:
- FDA: https://www.fda.gov/media/96771/download
- AJKD/PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC12101959/

Inspect the fetched source content before proposing a contract. Do not broaden into exploratory search unless a target fetch cannot establish the source.

Use only /tmp/evidencepatch_video_demo for a disposable synthetic repository. First check whether that path exists. If it exists, STOP; do not delete or overwrite it. Otherwise create canonical and candidate directories. Put in canonical only a minimal synthetic Python rule matching the controlling FDA behavior for an existing metformin user when eGFR later falls below 30 mL/min/1.73 m2. Copy canonical to candidate byte-for-byte and do not modify candidate afterward.

Construct the proposed contract from the fetched evidence. Use the FDA item as AUTHORITATIVE/CURRENT with proposes_executable_change=false and conflicts_with_current_authority=false if the fetched source still supports those fields. Use DOI 10.1053/j.ajkd.2024.08.012 as NON_AUTHORITATIVE/CURRENT with proposes_executable_change=true and conflicts_with_current_authority=true only if the fetched published paper still supports those fields. Keep publication lifecycle status distinct from evidentiary strength. At contract level, use executable_behavior_change=false, semantic_equivalence=true, unresolved_conflict=false, and ambiguous_or_incomplete=false only if the evidence and synthetic repository still support them. Do not choose the final action yourself.

Call the actual EvidencePatch MCP tools in this order:
1. assess_change_contract with the complete proposed contract.
2. analyze_repository_impact with canonical_repo=/tmp/evidencepatch_video_demo/canonical and candidate_repo=/tmp/evidencepatch_video_demo/candidate.
3. verify_result_provenance with the same contract and repositories, constructing schema_version=1 result fields directly from the exact assess_change_contract response, changed_files=[], evidence_ids in returned order, the returned human_review_required value, and a short software-maintenance/not-medical-advice summary.

Report the actual returned action, human-review flag, repository-impact result, overall provenance result, and every provenance check. Do not fabricate or force the canonical historical result if the live tools return something different. Confirm no tracked file changed, no production clinical repository changed, no deployment occurred, and no patient-specific recommendation was made.
```

## 3:30–4:10 — Human checkpoint and reproducibility

**Show:** `docs/public_mcp_demo.md`, then `docs/reproducibility.md` and `artifacts/official/README.md`.

**Say:**

“In the reviewed original demo, the host initially marked the fully published paper `PROVISIONAL`. Human review corrected it to `CURRENT` while retaining `NON_AUTHORITATIVE`. There was no Exa re-search during that correction and no repository modification. The same deterministic tools reran, the action remained `ESCALATE`, and all five provenance checks passed.

“The benchmark implementation is pinned by tag and commit; prompt hashes and no-retry policy are recorded; official public artifacts are byte-identical snapshots. The scoped project suite has 685 passing tests, and benchmark cases are validated separately. Historical dollar cost was not captured, so we report calls and solver duration rather than inventing a cost.”

## 4:10–4:40 — Safety boundary and closing insight

**Show:** README Safety/Scope and final thesis.

**Say:**

“Consequential changes remain sandboxed and human reviewed. `PATCH` is authorization for a separate implementation stage, not deployment permission; `ESCALATE` is also a human checkpoint. This synthetic benchmark and public demo do not establish clinical safety.

“EvidencePatch is not a medical decision maker. It is an evidence-to-code verification boundary: Exa finds evidence, agents interpret it, deterministic governance decides whether software change is authorized, and provenance checks verify what actually changed. In consequential maintenance, ‘no code change’ is not a complete outcome category.”

## Video Recording Notes

- Record at 1080p if available.
- Increase terminal and browser font size.
- Hide API keys and environment secrets.
- Do not show hidden benchmark directories.
- Do not run the full benchmark live.
- Pre-open `README.md`, `artifacts/official/comparison.md`, `CHANGELOG.md`, `docs/trajectories.md`, `docs/public_mcp_demo.md`, and `docs/reproducibility.md`.
- Use only the real public MCP execution with disposable `/tmp` paths.
- Show actual tool responses; never hard-code or fake a response.
- If the live result is unexpected, report it accurately.
- Keep the final recording under five minutes.
- Avoid scrolling through source code unless directly relevant.
