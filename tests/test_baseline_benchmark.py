from dataclasses import FrozenInstanceError
import hashlib
import json
import math
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import evidencepatch.baseline_benchmark as baseline_module
from evidencepatch.baseline_benchmark import run_baseline_benchmark
from evidencepatch.baseline_prompt import BASELINE_PROMPT
from evidencepatch.codex_runner import CodexRunResult
from evidencepatch.evaluation_types import CaseEvaluation, EvaluationCheck


CASES = PROJECT_ROOT / "benchmark" / "cases"
CHECK_NAMES = (
    "action_correct",
    "evidence_ids_correct",
    "human_review_correct",
    "declared_changes_match_actual",
    "production_impact_correct",
    "no_unexpected_repository_changes",
    "hidden_behavior_passed",
)


def _evaluation(case_id, failed=()):
    return CaseEvaluation(
        case_id,
        tuple(
            EvaluationCheck(name, name not in failed, f"Detail for {name}")
            for name in CHECK_NAMES
        ),
    )


def _install_fakes(
    monkeypatch,
    *,
    evaluations=None,
    returncode=0,
    timed_out=False,
    mutate_workspace=None,
):
    codex_calls = []
    evaluation_calls = []
    order = []
    evaluations = evaluations or {}

    def fake_run_codex(
        workspace, artifacts_dir, prompt, *, model, timeout_seconds
    ):
        order.append(("codex", workspace))
        codex_calls.append(
            {
                "workspace": workspace,
                "artifacts_dir": artifacts_dir,
                "prompt": prompt,
                "model": model,
                "timeout_seconds": timeout_seconds,
                "workspace_names": {path.name for path in workspace.iterdir()},
                "hidden_present": (workspace / "hidden").exists(),
                "ground_truth_files": list(workspace.rglob("ground_truth.json")),
            }
        )
        artifacts_dir.mkdir(parents=True)
        prompt_path = artifacts_dir / "prompt.txt"
        events_path = artifacts_dir / "events.jsonl"
        stderr_path = artifacts_dir / "stderr.txt"
        metadata_path = artifacts_dir / "run_metadata.json"
        prompt_path.write_text(prompt)
        events_path.write_text('{"event":"fake"}\n')
        stderr_path.write_text("")
        metadata_path.write_text("{}\n")
        if mutate_workspace is not None:
            mutate_workspace(workspace)
        return CodexRunResult(
            model=model,
            codex_version="codex-cli fake",
            returncode=returncode,
            timed_out=timed_out,
            duration_seconds=1.25,
            events_path=events_path,
            stderr_path=stderr_path,
            prompt_path=prompt_path,
            metadata_path=metadata_path,
        )

    def fake_evaluate_case(case_dir, workspace, *, hidden_timeout_seconds):
        order.append(("evaluate", workspace))
        evaluation_calls.append(
            {
                "case_dir": case_dir,
                "workspace": workspace,
                "hidden_timeout_seconds": hidden_timeout_seconds,
            }
        )
        return evaluations.get(case_dir.name, _evaluation(case_dir.name))

    monkeypatch.setattr(baseline_module, "run_codex", fake_run_codex)
    monkeypatch.setattr(baseline_module, "evaluate_case", fake_evaluate_case)
    return codex_calls, evaluation_calls, order


def test_frozen_prompt_order_invocations_and_workspace_isolation(tmp_path, monkeypatch):
    calls, evaluations, order = _install_fakes(monkeypatch)
    case_dirs = (
        CASES / "case_12",
        CASES / "case_01",
        CASES / "case_10",
    )

    run = run_baseline_benchmark(
        case_dirs,
        tmp_path / "output",
        model="model-x",
        codex_timeout_seconds=12,
        hidden_timeout_seconds=7,
    )

    expected_hash = hashlib.sha256(BASELINE_PROMPT.encode("utf-8")).hexdigest()
    assert run.prompt_sha256 == expected_hash
    assert tuple(case.case_id for case in run.cases) == (
        "case_12",
        "case_01",
        "case_10",
    )
    assert len(calls) == 3
    assert len(evaluations) == 3
    assert len({str(call["workspace"]) for call in calls}) == 3
    for call in calls:
        assert call["prompt"] == BASELINE_PROMPT
        assert call["model"] == "model-x"
        assert call["timeout_seconds"] == 12
        assert call["workspace_names"] == {
            "task.md",
            "evidence",
            "repo",
        }
        assert call["hidden_present"] is False
        assert call["ground_truth_files"] == []
    assert all(call["hidden_timeout_seconds"] == 7 for call in evaluations)
    assert [kind for kind, _ in order] == [
        "codex",
        "evaluate",
        "codex",
        "evaluate",
        "codex",
        "evaluate",
    ]
    summary = json.loads(run.summary_path.read_text())
    assert [case["case_id"] for case in summary["cases"]] == [
        "case_12",
        "case_01",
        "case_10",
    ]


@pytest.mark.parametrize(
    ("returncode", "timed_out"), [(None, True), (2, False)]
)
def test_timeout_or_nonzero_case_is_still_evaluated(
    tmp_path, monkeypatch, returncode, timed_out
):
    calls, evaluations, _ = _install_fakes(
        monkeypatch, returncode=returncode, timed_out=timed_out
    )

    run = run_baseline_benchmark(
        (CASES / "case_12",), tmp_path / "output"
    )

    assert len(calls) == 1
    assert len(evaluations) == 1
    assert run.cases[0].codex_run.returncode == returncode
    assert run.cases[0].codex_run.timed_out is timed_out
    if timed_out:
        assert run.timed_out_cases == ("case_12",)
        assert run.nonzero_exit_cases == ()
    else:
        assert run.nonzero_exit_cases == ("case_12",)


@pytest.mark.parametrize("solver_output", ["missing", "malformed"])
def test_invalid_solver_result_has_no_retry(tmp_path, monkeypatch, solver_output):
    def mutate(workspace):
        if solver_output == "malformed":
            (workspace / "evidencepatch_result.json").write_text("{invalid")

    failed = _evaluation("case_12", set(CHECK_NAMES))
    calls, evaluations, _ = _install_fakes(
        monkeypatch,
        evaluations={"case_12": failed},
        mutate_workspace=mutate,
    )

    run = run_baseline_benchmark(
        (CASES / "case_12",), tmp_path / "output"
    )

    assert len(calls) == 1
    assert len(evaluations) == 1
    assert run.evaluation.verified_successes == 0


def test_workspace_snapshot_and_evaluation_json_are_persisted(tmp_path, monkeypatch):
    def mutate(workspace):
        (workspace / "evidencepatch_result.json").write_text('{"fake":true}\n')

    _install_fakes(monkeypatch, mutate_workspace=mutate)

    run = run_baseline_benchmark(
        (CASES / "case_12",), tmp_path / "output"
    )
    case_run = run.cases[0]

    assert (case_run.workspace_snapshot / "task.md").is_file()
    assert (case_run.workspace_snapshot / "evidence").is_dir()
    assert (case_run.workspace_snapshot / "repo").is_dir()
    assert (
        case_run.workspace_snapshot / "evidencepatch_result.json"
    ).read_text() == '{"fake":true}\n'
    assert not (case_run.workspace_snapshot / "hidden").exists()
    evaluation_json = json.loads(case_run.evaluation_path.read_text())
    assert evaluation_json == {
        "schema_version": 1,
        "case_id": "case_12",
        "verified_success": True,
        "checks": [
            {"name": name, "passed": True, "detail": f"Detail for {name}"}
            for name in CHECK_NAMES
        ],
    }


def test_summary_uses_strict_vusr_and_check_metrics(tmp_path, monkeypatch):
    evaluations = {
        "case_10": _evaluation("case_10"),
        "case_12": _evaluation("case_12", {"hidden_behavior_passed"}),
    }
    _install_fakes(monkeypatch, evaluations=evaluations)

    run = run_baseline_benchmark(
        (CASES / "case_10", CASES / "case_12"), tmp_path / "output"
    )
    summary = json.loads(run.summary_path.read_text())

    assert summary["total_cases"] == 2
    assert summary["verified_successes"] == 1
    assert summary["verified_failures"] == 1
    assert summary["vusr"] == 0.5
    metrics = {metric["name"]: metric for metric in summary["check_metrics"]}
    assert metrics["action_correct"]["rate"] == 1.0
    assert metrics["hidden_behavior_passed"] == {
        "name": "hidden_behavior_passed",
        "passed_cases": 1,
        "total_cases": 2,
        "rate": 0.5,
    }
    assert run.total_duration_seconds == 2.5


def test_experiment_metadata_records_no_retry_or_feedback(tmp_path, monkeypatch):
    _install_fakes(monkeypatch)

    run = run_baseline_benchmark(
        (CASES / "case_12",),
        tmp_path / "output",
        codex_timeout_seconds=17,
        hidden_timeout_seconds=9,
    )
    metadata = json.loads(
        (run.output_dir / "experiment_metadata.json").read_text()
    )

    assert metadata["retry_policy"] == "none"
    assert metadata["solver_invocations_per_case"] == 1
    assert metadata["web_search_enabled"] is False
    assert metadata["human_feedback_during_run"] is False
    assert metadata["codex_timeout_seconds"] == 17
    assert metadata["hidden_timeout_seconds"] == 9


@pytest.mark.parametrize("output_kind", ["nonempty", "file", "symlink"])
def test_invalid_output_directory_is_rejected(tmp_path, monkeypatch, output_kind):
    output = tmp_path / "output"
    if output_kind == "nonempty":
        output.mkdir()
        (output / "existing.txt").write_text("existing\n")
    elif output_kind == "file":
        output.write_text("file\n")
    else:
        target = tmp_path / "target"
        target.mkdir()
        output.symlink_to(target, target_is_directory=True)
    _install_fakes(monkeypatch)

    with pytest.raises(ValueError, match="Output"):
        run_baseline_benchmark((CASES / "case_12",), output)


def test_output_overlapping_case_is_rejected(monkeypatch):
    _install_fakes(monkeypatch)
    output = CASES / "case_12" / "experiment_output"

    with pytest.raises(ValueError, match="inside a case"):
        run_baseline_benchmark((CASES / "case_12",), output)

    assert not output.exists()


def test_duplicate_case_names_are_rejected(tmp_path, monkeypatch):
    _install_fakes(monkeypatch)

    with pytest.raises(ValueError, match="names must be unique"):
        run_baseline_benchmark(
            (CASES / "case_12", CASES / "case_12"), tmp_path / "output"
        )


@pytest.mark.parametrize("timeout_name", ["codex", "hidden"])
@pytest.mark.parametrize("invalid_timeout", [0, -1, True, math.inf, math.nan])
def test_invalid_timeouts_are_rejected(
    tmp_path, timeout_name, invalid_timeout
):
    kwargs = {
        "codex_timeout_seconds": 10,
        "hidden_timeout_seconds": 10,
    }
    kwargs[f"{timeout_name}_timeout_seconds"] = invalid_timeout

    with pytest.raises(ValueError, match=f"{timeout_name}_timeout_seconds"):
        run_baseline_benchmark(
            (CASES / "case_12",), tmp_path / "output", **kwargs
        )


@pytest.mark.parametrize("invalid_model", ["", "   ", None, 1])
def test_invalid_model_is_rejected(tmp_path, invalid_model):
    with pytest.raises(ValueError, match="model.*non-empty"):
        run_baseline_benchmark(
            (CASES / "case_12",), tmp_path / "output", model=invalid_model
        )


def test_unsafe_workspace_symlink_is_never_dereferenced(tmp_path, monkeypatch):
    def mutate(workspace):
        external = workspace.parent / "external.txt"
        external.write_text("external\n")
        (workspace / "unsafe_link").symlink_to(external)

    calls, evaluations, _ = _install_fakes(
        monkeypatch, mutate_workspace=mutate
    )

    with pytest.raises(RuntimeError, match="cannot be safely persisted.*symlink"):
        run_baseline_benchmark(
            (CASES / "case_12",), tmp_path / "output"
        )

    assert len(calls) == 1
    assert len(evaluations) == 1
    assert not (tmp_path / "output" / "case_12" / "workspace").exists()


def test_returned_dataclasses_are_immutable(tmp_path, monkeypatch):
    _install_fakes(monkeypatch)
    run = run_baseline_benchmark(
        (CASES / "case_12",), tmp_path / "output"
    )

    with pytest.raises(FrozenInstanceError):
        run.model = "different"
    with pytest.raises(FrozenInstanceError):
        run.cases[0].case_id = "different"
