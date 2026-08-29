# EvidencePatch Final Submission Audit

Status vocabulary: **PASS** means supported by repository evidence; **ATTENTION** means a limitation or disclosure must remain visible; **MANUAL** means a human submission step is still outstanding. No numeric judge score is assigned here.

## Problem & User Value — 15

| Status | Check | Evidence |
| --- | --- | --- |
| PASS | Clear target user | Clinical-informatics engineers and healthcare-software maintenance teams are identified in README and submission copy. |
| PASS | Meaningful bottleneck | Evidence authority, executable delta, safe conflict handling, and repository provenance are separated explicitly. |
| PASS | Practical value | The product yields auditable `PATCH`, `NO_PATCH`, or `ESCALATE` maintenance dispositions and verifies repository impact. |

## Agent Solution & Engineering — 30

| Status | Check | Evidence |
| --- | --- | --- |
| PASS | OpenAI Codex explicitly identified | README, reproducibility guide, and submission copy identify OpenAI Codex CLI and `gpt-5.6-sol`. |
| PASS | Purposeful contract extraction agent | Codex converts public inputs into a Clinical Change Contract. |
| PASS | Deterministic governance | Frozen governance selects `PATCH`, `NO_PATCH`, or `ESCALATE`. |
| PASS | Authorized PATCH agent | A separate Codex stage runs only after `PATCH`; frozen case_01 trajectory shows the full path. |
| PASS | Exa MCP | Public evidence discovery/fetch responsibility is explicit. |
| PASS | EvidencePatch MCP | Three deterministic assessment, impact, and provenance tools are documented. |
| PASS | Verification | Repository impact and five provenance checks are represented in the public demo. |
| PASS | Sandboxing/isolation | Canonical/candidate isolation and sandboxed patch execution are documented. |
| PASS | Human review | Both `PATCH` and `ESCALATE` retain a human checkpoint. |
| PASS | No retry score chasing | Official retry policy is none; trajectories disclose no retries or hidden feedback. |

## End-to-End Quality — 20

| Status | Check | Evidence |
| --- | --- | --- |
| PASS | Real public evidence path | Reviewed FDA and AJKD sources are documented. |
| PASS | Executable MCP product | EvidencePatch MCP tools and registration instructions exist. |
| PASS | Useful final action | Public demo returned `ESCALATE` with human review required. |
| PASS | Repository impact | Canonical/candidate comparison returned clean. |
| PASS | Provenance verification | Public demo passed 5/5 checks. |
| PASS | PATCH path trajectory | Frozen advanced case_01 shows authorization, separate patch call, diff, and verified result. |
| PASS | ESCALATE path trajectory | Advanced case_10 and the public demo show escalation without a patch stage. |
| PASS | Video includes real execution | Demo script requires a real public terminal/MCP path and actual responses. |

## Measured Improvement — 15

| Status | Check | Evidence |
| --- | --- | --- |
| PASS | Fair simple baseline | One direct Codex solve per case. |
| PASS | Same model and cases | `gpt-5.6-sol`, same 12 synthetic cases. |
| PASS | Primary metric | Strict complete-case VUSR with seven required checks. |
| PASS | At least 10 cases | 12 cases. |
| PASS | Challenging case | case_10 was the only complete-case transition, FAIL → PASS. |
| PASS | Complete results | Baseline 11/12; advanced 12/12. |
| ATTENTION | Compute tradeoff | Advanced used 1.75× calls and 1.83× solver duration; not equal budget. |
| PASS | Improvement Changelog | `CHANGELOG.md` identifies stages, evidence, decisions, corrections, and compute cost. |
| PASS | Removed experiment/design | Model-controlled final disposition was not retained. |

## Reproducibility — 15

| Status | Check | Evidence |
| --- | --- | --- |
| PASS | Clean setup and canonical tests | Install command and `PYTHONPATH=. pytest tests -q`. |
| PASS | Baseline reproduction example | Clearly labeled expensive new model run with a new output directory. |
| PASS | Advanced reproduction example | Clearly labeled expensive new model run with a new output directory. |
| PASS | Agent/model identification | OpenAI Codex CLI and `gpt-5.6-sol`. |
| PASS | Runtime reporting | 595.405 and 1090.656 seconds. |
| ATTENTION | Cost transparency | Historical monetary API cost was not captured; no dollar estimate is invented. |
| PASS | Official tag/commit | `evidencepatch-advanced-official-v1` / `ff000f41d01ba7a351fdcc7a082e3fc046294941`. |
| PASS | Prompt hashes | Both frozen prompt SHA-256 values are documented. |
| PASS | Immutable artifact hashes | Official artifact manifest records five byte-identical snapshots and hashes. |
| PASS | Representative trajectories | Baseline, advanced escalation, advanced PATCH, and human-feedback MCP traces are present. |

## Hot Take / Insights — 5

| Status | Check | Evidence |
| --- | --- | --- |
| PASS | Main failure mode explicit | A capable agent can still choose the wrong maintenance disposition. |
| PASS | Practical lesson explicit | Governance taxonomy should be separated from code generation; “no code change” is incomplete without escalation. |

## Ground Rules

| Status | Check | Evidence |
| --- | --- | --- |
| PASS | Public/synthetic data | Benchmark is synthetic; product demo uses public FDA/AJKD sources. |
| PASS | No credential exposure | Documentation uses an API-key placeholder; tracked-secret audit found no actual credential-looking assignment. |
| PASS | Sandboxed consequential action | Patch workspaces are isolated; public demo uses disposable `/tmp` repositories. |
| PASS | Human review | Required for `PATCH` and `ESCALATE`. |
| PASS | Claims tied to evidence | Official summaries, comparison, provenance, trajectories, and hashes are linked. |
| PASS | Reproducibility access | Setup, validation, reproduction examples, and immutable artifacts are documented. |
| ATTENTION | Before-competition disclosure | Git history begins with a minimal README on 2026-08-29 and adds the project implementation afterward that day. Without an independently recorded competition window, no stronger categorical timing claim is made. External Codex, Exa, MCP SDK, and Python dependencies are distinguished from repository-specific work. |

## Final Deliverables

| Status | Deliverable |
| --- | --- |
| PASS | Complete solution code plus Improvement Changelog |
| PASS | Reproduction guide |
| PASS | Under-five-minute video script requiring real execution |
| PASS | Representative agent trajectories |

## Remaining Manual Submission Tasks

| Status | Task |
| --- | --- |
| MANUAL | Record the under-five-minute video. |
| MANUAL | Use the real terminal/MCP execution during recording. |
| MANUAL | Upload the video. |
| MANUAL | Ensure the video is publicly/viewably accessible as required. |
| MANUAL | Paste the submission description. |
| MANUAL | Provide the repository URL. |
| MANUAL | Verify repository visibility. |
| MANUAL | Verify no secrets are visible in the recording. |
| MANUAL | Verify no hidden benchmark files appear on screen. |
| MANUAL | Submit before the deadline. |

## Repository-History Disclosure

Current audit HEAD before this documentation pass: `a704cea83416f18d8e5768ab2904273fc2c53dfa`. Normal Git history starts at `ffd2a70` with a two-line README dated 2026-08-29. Subsequent commits on that date add benchmark cases, evaluation, Codex runners, Clinical Change Contract/governance, advanced workflow, comparison reporting, EvidencePatch MCP, and documentation. This establishes the repository sequence, but the repository alone does not independently prove where that date falls relative to the competition window.
