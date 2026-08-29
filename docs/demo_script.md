# EvidencePatch Demo Script

Target runtime: **4:30–4:50**. Hard maximum: **under 5:00**.

The recording uses saved artifacts and documentation; it does not depend on an expensive benchmark run. If a live MCP segment is used, keep it short, deterministic, read-only, and confined to disposable paths.

## 0:00–0:30 — Problem and user

**Show:** the top of `README.md` and its thesis.

**Say:**

“Clinical-informatics engineers have to translate changing evidence into executable software rules. But fresh evidence is not automatically actionable evidence. A new study can matter without superseding the regulator or guideline that controls today's software behavior. EvidencePatch governs that evidence-to-code maintenance boundary; it does not make clinical decisions.”

## 0:30–1:10 — Architecture

**Show:** the Mermaid diagram in `README.md` or `docs/architecture.md`.

**Say:**

“The surfaces have separate responsibilities. Exa discovers and fetches public evidence. A host or agent proposes a structured interpretation as a Clinical Change Contract. EvidencePatch applies deterministic governance and provenance verification. In the measured agent workflow, Codex receives a separate patch call only after governance authorizes `PATCH`. EvidencePatch MCP itself does not search, invoke Codex, modify repositories, or deploy software.”

## 1:10–1:55 — Measured improvement

**Show:** `artifacts/official/comparison.md`.

**Say exactly:**

“Plain Codex: 11 out of 12, or 91.67% VUSR. EvidencePatch: 12 out of 12, or 100%. The measured change is plus 8.33 percentage points.”

Immediately disclose:

“Calls increased from 12 to 21, or 1.75 times. Solver duration increased from 595.405 to 1090.656 seconds, or 1.83 times. This is a reliability-versus-compute tradeoff on a 12-case synthetic benchmark, not a statistical or clinical-safety claim.”

## 1:55–2:40 — Why the improvement happened

**Show:** the baseline and advanced case_10 sections in `docs/trajectories.md`.

**Say:**

“The baseline's only complete-case failure was `action_correct`. The public baseline summary does not retain its submitted action, so we do not infer it. What the trace establishes is that direct one-shot solving selected the wrong maintenance disposition according to `action_correct`; the permitted public artifact does not retain the submitted action, so we do not reconstruct it.

“The advanced path made the interpretation explicit: controlling authority matched the repository, while weaker evidence created conflicting change pressure. Deterministic governance selected `ESCALATE`; there was no patch call. The case passed every check, and no retry or hidden evaluator feedback was used.”

Briefly point to the full PATCH trace:

“A separate successful trace shows the other branch: authoritative executable delta, deterministic `PATCH` authorization, then one separately authorized implementation call.”

## 2:40–3:55 — Real public Exa + EvidencePatch MCP demo

**Show:** `docs/public_mcp_demo.md`, or a terminal with already-configured MCP tools and disposable paths.

**Say:**

“The public example concerns metformin and eGFR below 30. The FDA source controls current executable behavior. A newer published AJKD observational study creates credible conflicting pressure while acknowledging residual confounding and calling for randomized confirmation.

“Exa discovered and fetched the sources. The host proposed the contract. EvidencePatch returned `ESCALATE`; the candidate repository stayed identical to canonical, and five out of five provenance checks passed.

“The human checkpoint matters. The host initially marked the published paper `PROVISIONAL`. Human review corrected its lifecycle status to `CURRENT` while keeping it `NON_AUTHORITATIVE`. The corrected contract went back through the same deterministic tools. The result remained `ESCALATE`, and no repository change occurred. The tool absorbed corrected human interpretation without silently changing software.”

Do not turn this segment into treatment advice.

## 3:55–4:25 — Engineering and reproducibility

**Show:** `docs/reproducibility.md`, then `artifacts/official/README.md`.

**Say:**

“The benchmark implementation is pinned by an official tag. Prompt hashes and the no-retry policy are recorded. The public artifacts are byte-identical snapshots of historical summaries and provenance. The scoped project regression suite has 685 passing tests, and benchmark cases are validated separately. The MCP server is deterministic and read-only with respect to repositories.”

## 4:25–4:45 — Close

**Show:** the README thesis or architecture boundary.

**Say:**

“EvidencePatch is not a medical decision maker. It is an evidence-to-code verification boundary: Exa finds evidence, agents interpret it, deterministic governance decides whether software change is authorized, and provenance checks verify what actually changed.”

## Video Recording Notes

- Record at 1080p if available.
- Increase terminal and browser font size.
- Hide API keys and environment secrets.
- Do not show hidden benchmark directories.
- Do not run the full benchmark live.
- Pre-open `README.md`, `artifacts/official/comparison.md`, `docs/trajectories.md`, and `docs/public_mcp_demo.md`.
- If showing MCP live, use only deterministic/read-only calls with disposable paths.
- Keep the final recording under five minutes.
- Avoid scrolling through source code unless directly relevant.
