# Official Public Artifact Snapshots

These files are immutable public snapshots copied from saved historical runs for auditability. Every snapshot is a byte-for-byte copy; the source run directories were not modified.

| Destination | Original source | SHA-256 | Purpose |
| --- | --- | --- | --- |
| `baseline_benchmark_summary.json` | `runs/plain_codex_baseline_gpt56sol_20260829_final_rescore/benchmark_summary.json` | `ae8f7400542a8ff79d78304cb7cdf6051ef92726b650d8c12dbf71f5888b1f1e` | Official rescored plain Codex baseline summary. |
| `advanced_benchmark_summary.json` | `runs/evidencepatch_advanced_gpt56sol_20260829/benchmark_summary.json` | `e5e3493302386d7e7c59b636b5f7116118bfec9611e9c407e807f0ae25cdd57a` | Official EvidencePatch advanced benchmark summary. |
| `advanced_run_provenance.json` | `runs/evidencepatch_advanced_gpt56sol_20260829/run_provenance.json` | `e89f3cba8fbf8e27c58719a3eff31c121c170a8704596fee870ad200fc8809ac` | Commit, prompt, policy, and run-integrity provenance. |
| `comparison.json` | `runs/evidencepatch_measured_improvement_20260829/comparison.json` | `886766e7cabdbe7297db4ebbf4ac660e99acb86df4d91584ffb472f940bc2093` | Machine-readable deterministic comparison. |
| `comparison.md` | `runs/evidencepatch_measured_improvement_20260829/comparison.md` | `8f632e6fae6bfe14fb71c59019581a9295ad838d31fa056ef4597befbe26a62f` | Human-readable deterministic comparison. |

No hidden ground truth is included. These snapshots do not permit solver access to hidden evaluation data. The historical advanced benchmark implementation is pinned by tag `evidencepatch-advanced-official-v1`; later documentation and product work do not alter that recorded experiment.
