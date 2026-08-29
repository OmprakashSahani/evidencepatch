# EvidencePatch

Fresh medical evidence is not automatically actionable medical evidence.

EvidencePatch governs evidence-backed maintenance of clinical-informatics and healthcare software. Its focus is not merely generating code, but establishing whether controlling evidence supports an executable behavior change, handling weaker conflicting evidence safely, and checking that repository changes match their declared provenance. It does not make clinical decisions.

## What EvidencePatch Does

EvidencePatch represents proposed evidence interpretations as a Clinical Change Contract, applies deterministic governance, and verifies the declared result against repository state. The possible dispositions are `PATCH`, `NO_PATCH`, and `ESCALATE`; both `PATCH` and `ESCALATE` require human review.

## Why This Exists

Recency, publication, and authority are different properties. A new peer-reviewed study can create meaningful change pressure without superseding a current regulator or guideline rule. Clinical-software maintenance needs an explicit boundary between discovering evidence, interpreting it, authorizing a change, and verifying what actually changed.

## Architecture

The measured workflow and product MCP surface are related but distinct:

```mermaid
flowchart LR
  subgraph Benchmark[Measured advanced benchmark workflow]
    A[Public synthetic task<br/>evidence + repository] --> B[Codex contract extraction]
    B --> C[Clinical Change Contract]
    C --> D[Frozen deterministic governance]
    D --> E{PATCH?}
    E -->|yes| F[Separate authorized Codex patch stage]
    E -->|no| G[Deterministic result]
    F --> G
    G --> H[Static provenance checks]
    H --> I[Hidden behavior test]
    I --> J[VUSR]
  end
  subgraph Product[Product MCP surface]
    X[Exa MCP<br/>public discovery/fetch] --> Y[Host/agent<br/>proposed interpretation]
    Y --> Z[EvidencePatch MCP<br/>govern + compare + verify]
  end
```

See [Architecture](docs/architecture.md) for the full boundaries and action taxonomy.

## Agent Stack

- Coding/reasoning agent: OpenAI Codex CLI
- Official benchmark model: `gpt-5.6-sol`
- Baseline: one direct Codex solve per benchmark case
- Advanced workflow: Codex contract-extraction agent → deterministic EvidencePatch governance → separate authorized Codex patch agent only when `action = PATCH`
- Public evidence discovery: Exa MCP
- Governance and repository verification: EvidencePatch MCP
- Official benchmark retry policy: none

Codex is used purposefully for semantic interpretation and implementation; final disposition governance and provenance rules are deterministic. EvidencePatch MCP is a governance and verification surface, not a coding agent.

## Measured Result

On 12 synthetic medication-safety and clinical-software maintenance cases with `gpt-5.6-sol`:

| Workflow | VUSR | Verified cases |
| --- | ---: | ---: |
| Plain Codex | 91.67% | 11/12 |
| EvidencePatch advanced | 100.00% | 12/12 |
| Measured delta | **+8.33 percentage points** | failures 1 → 0 |

The improvement has a direct compute tradeoff: **1.75× Codex calls** (12 → 21) and **1.83× solver duration** (595.405 → 1090.656 seconds). This is a reliability-versus-compute result, not an equal-inference-budget comparison. It is not a claim of statistical significance or clinical safety.

See the [official comparison](artifacts/official/comparison.md) and [evaluation documentation](docs/evaluation.md).

## Main Failure Mode and Hot Take

**Main failure mode:** a capable agent can still choose the wrong software-maintenance disposition even when most of the task is handled correctly. The baseline's only complete-case failure was `action_correct`; the permitted public artifact does not retain the submitted action, so it is not reconstructed.

**Hot take:** in consequential software maintenance, “no code change” is not a complete outcome category. Some evidence states require explicit escalation, and the boundary between `PATCH`, `NO_PATCH`, and `ESCALATE` should be governed separately from code generation. This follows the central thesis: fresh medical evidence is not automatically actionable medical evidence.

## Removed Experiment

The simple baseline let one direct Codex solve choose the final maintenance disposition itself. It reached 11/12 complete-case success, with the sole failure on `action_correct`. The final architecture did not retain model-controlled final disposition: Codex proposes the Clinical Change Contract, then deterministic governance selects `PATCH`, `NO_PATCH`, or `ESCALATE`.

The design lesson was that generation and governance should not necessarily be the same responsibility. This does not imply that the baseline misunderstood the medical evidence, and its unavailable submitted action is not inferred.

## MCP Product Surface

Exa MCP performs public evidence discovery and fetching. The host or agent constructs the proposed structured interpretation. EvidencePatch MCP then provides exactly three deterministic tools:

- `assess_change_contract`
- `analyze_repository_impact`
- `verify_result_provenance`

EvidencePatch MCP does not search the web, call Exa or Codex, modify repositories, deploy software, or read benchmark ground truth.

## Public Evidence Demo

The canonical public demo concerns metformin when eGFR falls below 30 mL/min/1.73 m². A current FDA rule says to discontinue metformin for an existing user below that threshold. A later published observational AJKD study supports possible continuation while noting residual confounding and the need for randomized confirmation. The corrected contract classifies both sources as `CURRENT`, but only the FDA source as `AUTHORITATIVE`. EvidencePatch returned `ESCALATE`, the unchanged synthetic repositories compared cleanly, and all five provenance checks passed. This is a software-maintenance disposition, not treatment advice.

See [Public MCP demo](docs/public_mcp_demo.md).

## Quick Start

```bash
python -m pip install -r requirements.txt
PYTHONPATH=. pytest tests -q
```

Register the local EvidencePatch MCP server:

```bash
PYTHON_BIN="$(command -v python)"
codex mcp add evidencepatch \
  --env PYTHONPATH="$PWD" \
  -- "$PYTHON_BIN" -m evidencepatch.mcp_server
```

Register Exa using API-key environment authentication:

```bash
export EXA_API_KEY=...

codex mcp add exa \
  --url 'https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa' \
  --bearer-token-env-var EXA_API_KEY
```

Do not put a real key in repository files. Hosted OAuth localhost callbacks can be awkward in remote Codespaces environments; environment-token authentication was used for the recorded public demo.

## Reproducibility

The historical evidence is preserved as immutable copies in [official artifacts](artifacts/official/README.md). Setup, validation, MCP inspection, and clearly labeled expensive reproduction examples are in [Reproducibility](docs/reproducibility.md).

## Hackathon Scope

Normal Git history begins with a minimal README in commit `ffd2a70` on 2026-08-29. Subsequent commits that day add the EvidencePatch benchmark, evaluator, Clinical Change Contract, governance, runners, workflow, comparison, MCP server, and public documentation. Git history therefore establishes that the project-specific implementation in this repository was built after that initial commit; without an independently recorded competition window, this submission does not make a stronger categorical timing claim.

OpenAI Codex CLI, Exa MCP, the MCP SDK, and Python ecosystem dependencies are external components. The project-specific EvidencePatch contracts, deterministic governance, isolated agent workflow, evaluation harness, MCP server, public demo, and audit documentation are implemented in this repository.

## Safety / Scope

- The measured benchmark is synthetic.
- The MCP demonstration uses public evidence and a disposable synthetic repository.
- EvidencePatch does not auto-deploy software.
- `PATCH` and `ESCALATE` governance require human review.
- Outputs are not medical advice.
- Benchmark performance does not establish clinical safety.

## Repository Guide

- [Architecture](docs/architecture.md)
- [Evaluation](docs/evaluation.md)
- [Reproducibility](docs/reproducibility.md)
- [Public MCP demo](docs/public_mcp_demo.md)
- [Representative trajectories](docs/trajectories.md)
- [Under-five-minute demo script](docs/demo_script.md)
- [Submission copy](docs/submission.md)
- [Final submission audit](docs/final_audit.md)
- [Improvement Changelog](CHANGELOG.md)
- [Official artifact snapshots](artifacts/official/README.md)
- [Official comparison](artifacts/official/comparison.md)
