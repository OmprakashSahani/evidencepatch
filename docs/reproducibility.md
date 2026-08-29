# Reproducibility

## Environment and tests

Use a supported Python environment with the repository as the working directory:

```bash
python -m pip install -r requirements.txt
PYTHONPATH=. pytest tests -q
```

Repository-root unscoped `pytest -q` is intentionally not recommended because isolated benchmark fixtures and saved experimental workspaces may contain their own test files. Scoping collection to `tests/` runs the EvidencePatch project regression suite. Benchmark cases are validated separately with `evidencepatch.case_validation.validate_case`.

Validate the structure of Cases 01–12 with the existing validator:

```python
from pathlib import Path

from evidencepatch.case_validation import validate_case

case_root = Path("benchmark/cases")
for number in range(1, 13):
    validate_case(case_root / f"case_{number:02d}")
print("Cases 01-12 valid")
```

Validation reads benchmark-private material internally; it should be run as a validation step, not exposed to solver workspaces.

## MCP server

Start EvidencePatch directly:

```bash
python -m evidencepatch.mcp_server
```

Or register both MCP servers with Codex:

```bash
PYTHON_BIN="$(command -v python)"
codex mcp add evidencepatch \
  --env PYTHONPATH="$PWD" \
  -- "$PYTHON_BIN" -m evidencepatch.mcp_server

export EXA_API_KEY=...
codex mcp add exa \
  --url 'https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa' \
  --bearer-token-env-var EXA_API_KEY
```

Inspect registrations without running a demo:

```bash
codex mcp list
codex mcp get exa
codex mcp get evidencepatch
```

Do not commit credentials. Hosted OAuth localhost callbacks can be awkward in remote Codespaces environments; environment-token authentication was used for the recorded demo.

## Official experiment provenance

The benchmark implementation is pinned by tag `evidencepatch-advanced-official-v1` at source commit `ff000f41d01ba7a351fdcc7a082e3fc046294941`. Historical measured outputs are preserved as byte-for-byte copies under [official artifacts](../artifacts/official/README.md). Later documentation and MCP product work on `main` do not redefine the frozen historical run.

## Baseline reproduction example

> **EXPENSIVE MODEL RUN — creates new experimental outputs and is not the historical official run.**

Do not run this merely to inspect the preserved result. It invokes Codex once for every case and writes a new output directory.

```bash
python - <<'PY'
from pathlib import Path

from evidencepatch.baseline_benchmark import run_baseline_benchmark

cases = tuple(Path("benchmark/cases") / f"case_{n:02d}" for n in range(1, 13))
run_baseline_benchmark(
    cases,
    Path("runs/reproduction_baseline"),
    model="gpt-5.6-sol",
)
PY
```

## Advanced reproduction example

> **EXPENSIVE MODEL RUN — creates new experimental outputs and is not the historical official run.**

This invokes structured extraction for each case and invokes a separate patch call when deterministic governance authorizes `PATCH`.

```bash
python - <<'PY'
from pathlib import Path

from evidencepatch.advanced_benchmark import run_advanced_benchmark

cases = tuple(Path("benchmark/cases") / f"case_{n:02d}" for n in range(1, 13))
run_advanced_benchmark(
    cases,
    Path("runs/reproduction_advanced"),
    model="gpt-5.6-sol",
)
PY
```

The example destinations intentionally do not reuse historical official run directories. The recorded figures should be audited from `artifacts/official/`, not regenerated in place.
