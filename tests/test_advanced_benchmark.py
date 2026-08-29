import json
import math
import shutil
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

import evidencepatch.advanced_benchmark as harness
from evidencepatch.advanced_benchmark import (
    AdvancedBenchmarkRun,
    AdvancedCaseRun,
    run_advanced_benchmark,
)
from evidencepatch.benchmark_evaluation import aggregate_case_evaluations
from evidencepatch.change_contract import ChangeAction
from evidencepatch.codex_runner import CodexRunResult
from evidencepatch.contract_extraction import CONTRACT_FILENAME, contract_from_mapping, contract_to_json
from evidencepatch.contract_runner import ContractExtractionRun
from evidencepatch.evaluation_types import CaseEvaluation, EvaluationCheck
from evidencepatch.patch_runner import AuthorizedPatchRun
from evidencepatch.repo_diff import compare_repositories
from evidencepatch.result_contract import RESULT_FILENAME, validate_solver_result
from evidencepatch.workflow import EvidencePatchWorkflowRun


CHECKS = (
    "action_correct", "evidence_ids_correct", "human_review_correct",
    "declared_changes_match_actual", "production_impact_correct",
    "no_unexpected_repository_changes", "hidden_behavior_passed",
)


def make_case(root: Path, name: str) -> Path:
    case = root / name
    (case / "evidence").mkdir(parents=True)
    (case / "repo" / "rules").mkdir(parents=True)
    (case / "task.md").write_text("Synthetic maintenance task.\n", encoding="utf-8")
    (case / "evidence" / "source.md").write_text("Synthetic evidence.\n", encoding="utf-8")
    (case / "repo" / "rules" / "rule.py").write_text("VALUE = 1\n", encoding="utf-8")
    return case


def contract(action: ChangeAction):
    return contract_from_mapping({
        "schema_version": 1,
        "evidence": [{
            "evidence_id": "SYNTHETIC-SOURCE",
            "authority": "DRAFT" if action is ChangeAction.ESCALATE else "AUTHORITATIVE",
            "status": "PROVISIONAL" if action is ChangeAction.ESCALATE else "CURRENT",
            "proposes_executable_change": action is not ChangeAction.NO_PATCH,
            "conflicts_with_current_authority": False,
        }],
        "executable_behavior_change": action is ChangeAction.PATCH,
        "semantic_equivalence": action is ChangeAction.NO_PATCH,
        "unresolved_conflict": False,
        "ambiguous_or_incomplete": False,
        "rationale": "Generic structured evidence rationale.",
    })


def codex(artifacts: Path, *, duration=1.0, timed_out=False, returncode=0) -> CodexRunResult:
    artifacts.mkdir(parents=True, exist_ok=True)
    paths = [artifacts / name for name in ("events.jsonl", "stderr.txt", "prompt.txt", "metadata.json")]
    for path in paths: path.write_text("", encoding="utf-8")
    return CodexRunResult("synthetic-model", "codex test", returncode, timed_out,
        duration, paths[0], paths[1], paths[2], paths[3])


def fake_workflow(workspace: Path, canonical: Path, extraction_artifacts: Path,
                  patch_artifacts: Path, action: ChangeAction | None,
                  *, fail=False, timeout_stage=None, nonzero_stage=None) -> EvidencePatchWorkflowRun:
    value = contract(action or ChangeAction.NO_PATCH)
    (workspace / CONTRACT_FILENAME).write_text(contract_to_json(value), encoding="utf-8")
    extraction_codex = codex(extraction_artifacts, duration=1.0,
        timed_out=timeout_stage == "extraction",
        returncode=None if timeout_stage == "extraction" else (2 if nonzero_stage == "extraction" else 0))
    digest = "a" * 64
    if fail and action is None:
        extraction = ContractExtractionRun(extraction_codex, None, workspace / CONTRACT_FILENAME,
            digest, digest, digest, True, "extraction failed")
        return EvidencePatchWorkflowRun(extraction, None, None, None,
            workspace / RESULT_FILENAME, "workflow failed")
    extraction = ContractExtractionRun(extraction_codex, value, workspace / CONTRACT_FILENAME,
        digest, digest, digest, True, None)
    patch = None
    changed = []
    if action is ChangeAction.PATCH:
        (workspace / "repo" / "rules" / "rule.py").write_text("VALUE = 2\n", encoding="utf-8")
        patch_codex = codex(patch_artifacts, duration=2.0,
            timed_out=timeout_stage == "patch",
            returncode=None if timeout_stage == "patch" else (3 if nonzero_stage == "patch" else 0))
        if fail:
            patch = AuthorizedPatchRun(patch_codex, None, digest, digest, digest, digest, True, "patch failed")
            return EvidencePatchWorkflowRun(extraction, ChangeAction.PATCH, patch, None,
                workspace / RESULT_FILENAME, "workflow failed")
        diff = compare_repositories(canonical, workspace / "repo")
        patch = AuthorizedPatchRun(patch_codex, diff, digest, digest, digest, digest, True, None)
        changed = list(diff.changed_files)
    result = validate_solver_result({
        "schema_version": 1, "action": action.value, "changed_files": changed,
        "evidence_ids": ["SYNTHETIC-SOURCE"],
        "human_review_required": action is not ChangeAction.NO_PATCH,
        "summary": f"{action.value}: {value.rationale}",
    })
    (workspace / RESULT_FILENAME).write_text(json.dumps({
        "schema_version": result.schema_version, "action": result.action,
        "changed_files": list(result.changed_files), "evidence_ids": list(result.evidence_ids),
        "human_review_required": result.human_review_required, "summary": result.summary,
    }), encoding="utf-8")
    return EvidencePatchWorkflowRun(extraction, action, patch, result,
        workspace / RESULT_FILENAME, None)


def evaluation(case_id: str, passed=True) -> CaseEvaluation:
    return CaseEvaluation(case_id, tuple(
        EvaluationCheck(name, passed, f"{name} diagnostic") for name in CHECKS
    ))


def install(monkeypatch: pytest.MonkeyPatch, actions, *, failures=(), eval_pass=None,
            timeout_stages=None, nonzero_stages=None):
    events = []; workflow_calls = []; evaluation_calls = []
    monkeypatch.setattr(harness, "validate_case", lambda case: None)
    def run(workspace, canonical, extraction_artifacts, patch_artifacts, **kwargs):
        case_id = workspace.parent.name if workspace.parent.name in actions else None
        # Temporary parent names are opaque, so match calls by sequence.
        index = len(workflow_calls); action = actions[index]
        events.append(("workflow", index)); workflow_calls.append((workspace, canonical, extraction_artifacts, patch_artifacts, kwargs))
        assert (extraction_artifacts.parents[1] / "experiment_metadata.json").exists()
        assert {p.name for p in workspace.iterdir()} == {"task.md", "evidence", "repo"}
        assert workspace != canonical
        assert compare_repositories(canonical, workspace / "repo").is_clean
        return fake_workflow(workspace, canonical, extraction_artifacts, patch_artifacts,
            action, fail=index in failures,
            timeout_stage=(timeout_stages or {}).get(index),
            nonzero_stage=(nonzero_stages or {}).get(index))
    def evaluate(case_dir, workspace, *, hidden_timeout_seconds):
        index = len(evaluation_calls); events.append(("evaluation", index))
        evaluation_calls.append((case_dir, workspace, hidden_timeout_seconds))
        return evaluation(case_dir.name, True if eval_pass is None else eval_pass[index])
    monkeypatch.setattr(harness, "run_evidencepatch_workflow", run)
    monkeypatch.setattr(harness, "evaluate_case", evaluate)
    return events, workflow_calls, evaluation_calls


def test_one_case_success_and_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case(tmp_path / "cases", "synthetic_a")
    events, workflows, evaluations = install(monkeypatch, [ChangeAction.NO_PATCH])
    run = run_advanced_benchmark((case,), tmp_path / "output")
    assert run.evaluation.vusr == 1.0 and run.cases[0].verified_success
    assert events == [("workflow", 0), ("evaluation", 0)]
    assert len(workflows) == len(evaluations) == 1
    assert run.cases[0].workspace_snapshot.exists()
    assert run.cases[0].evaluation_path.exists() and run.cases[0].workflow_metadata_path.exists()


def test_multiple_cases_preserve_order_and_one_call_each(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "cases"
    cases = tuple(make_case(root, name) for name in ("third", "first", "second"))
    events, workflows, evaluations = install(monkeypatch,
        [ChangeAction.ESCALATE, ChangeAction.NO_PATCH, ChangeAction.PATCH])
    run = run_advanced_benchmark(cases, tmp_path / "output")
    assert tuple(case.case_id for case in run.cases) == ("third", "first", "second")
    assert len(workflows) == len(evaluations) == 3
    assert events == [("workflow", 0), ("evaluation", 0), ("workflow", 1), ("evaluation", 1), ("workflow", 2), ("evaluation", 2)]
    assert len({call[0] for call in workflows}) == 3


def test_forwarding_and_case_artifact_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case(tmp_path / "cases", "sample")
    _, workflows, evaluations = install(monkeypatch, [ChangeAction.PATCH])
    run_advanced_benchmark((case,), tmp_path / "output", model="chosen",
        extraction_timeout_seconds=11, patch_timeout_seconds=22, hidden_timeout_seconds=33)
    call = workflows[0]
    assert call[2] == tmp_path / "output" / "sample" / "extraction_codex"
    assert call[3] == tmp_path / "output" / "sample" / "patch_codex"
    assert call[4] == {"model": "chosen", "extraction_timeout_seconds": 11, "patch_timeout_seconds": 22}
    assert evaluations[0][2] == 33


def test_failed_workflow_is_evaluated_once_and_in_denominator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "cases"; cases = (make_case(root, "failed"), make_case(root, "passed"))
    events, workflows, evaluations = install(monkeypatch,
        [None, ChangeAction.NO_PATCH], failures={0}, eval_pass=[False, True])
    run = run_advanced_benchmark(cases, tmp_path / "output")
    assert len(workflows) == len(evaluations) == 2
    assert run.evaluation.total_cases == 2 and run.evaluation.vusr == 0.5
    assert run.workflow_failure_cases == ("failed",)
    assert (tmp_path / "output" / "failed" / "workspace").exists()


def test_public_only_workspace_and_canonical_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case(tmp_path / "cases", "public")
    (case / "hidden").mkdir(); (case / "hidden" / "ground_truth.json").write_text("private")
    _, workflows, _ = install(monkeypatch, [ChangeAction.NO_PATCH])
    run = run_advanced_benchmark((case,), tmp_path / "output")
    snapshot = run.cases[0].workspace_snapshot
    assert not (snapshot / "hidden").exists()
    assert not list(snapshot.rglob("ground_truth.json"))
    assert {p.name for p in snapshot.iterdir()} == {"task.md", "evidence", "repo", CONTRACT_FILENAME, RESULT_FILENAME}
    workspace, canonical = workflows[0][0], workflows[0][1]
    assert workspace != canonical


def test_metadata_written_before_workflow_and_contains_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case(tmp_path / "cases", "meta")
    install(monkeypatch, [ChangeAction.NO_PATCH])
    run = run_advanced_benchmark((case,), tmp_path / "output")
    data = json.loads(run.metadata_path.read_text())
    assert data["contract_extraction_prompt_sha256"] == harness.CONTRACT_EXTRACTION_PROMPT_SHA256
    assert data["authorized_patch_prompt_sha256"] == harness.AUTHORIZED_PATCH_PROMPT_SHA256
    assert data["retry_policy"] == "none"
    assert "expected_action" not in data


@pytest.mark.parametrize("action", [ChangeAction.NO_PATCH, ChangeAction.ESCALATE, ChangeAction.PATCH])
def test_workflow_json_observed_stage_and_solver_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: ChangeAction) -> None:
    case = make_case(tmp_path / "cases", "observed")
    install(monkeypatch, [action])
    run = run_advanced_benchmark((case,), tmp_path / "output")
    data = json.loads(run.cases[0].workflow_metadata_path.read_text())
    assert data["action"] == action.value and data["solver_result"]["action"] == action.value
    assert (data["patch"] is not None) is (action is ChangeAction.PATCH)
    assert data["extraction"]["prompt_sha256"] == harness.CONTRACT_EXTRACTION_PROMPT_SHA256


def test_failed_workflow_json_has_null_solver_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case(tmp_path / "cases", "failed")
    install(monkeypatch, [None], failures={0}, eval_pass=[False])
    run = run_advanced_benchmark((case,), tmp_path / "output")
    assert json.loads(run.cases[0].workflow_metadata_path.read_text())["solver_result"] is None


def test_evaluation_order_and_frozen_aggregation_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "cases"; cases = (make_case(root, "one"), make_case(root, "two"))
    install(monkeypatch, [ChangeAction.NO_PATCH, ChangeAction.PATCH], eval_pass=[True, False])
    calls = []
    real = harness.aggregate_case_evaluations
    monkeypatch.setattr(harness, "aggregate_case_evaluations", lambda values: calls.append(values) or real(values))
    run = run_advanced_benchmark(cases, tmp_path / "output")
    summary = json.loads(run.summary_path.read_text())
    assert len(calls) == 1 and summary["vusr"] == run.evaluation.vusr == 0.5
    assert summary["total_codex_calls"] == 3 and summary["total_codex_duration_seconds"] == 4.0
    assert summary["action_counts"] == {"PATCH": 1, "NO_PATCH": 1, "ESCALATE": 0, "UNRESOLVED": 0}
    evaluation_json = json.loads(run.cases[0].evaluation_path.read_text())
    assert [item["name"] for item in evaluation_json["checks"]] == list(CHECKS)


def test_unresolved_counts_timeout_and_nonzero_labels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "cases"; cases = (make_case(root, "unresolved"), make_case(root, "patched"))
    install(monkeypatch, [None, ChangeAction.PATCH], failures={0, 1}, eval_pass=[False, False],
        timeout_stages={0: "extraction"}, nonzero_stages={1: "patch"})
    run = run_advanced_benchmark(cases, tmp_path / "output")
    summary = json.loads(run.summary_path.read_text())
    assert summary["action_counts"]["UNRESOLVED"] == 1
    assert run.timed_out_invocations == ("unresolved:extraction",)
    assert run.nonzero_exit_invocations == ("patched:patch",)
    assert summary["cases"][0]["patch_returncode"] is None


def test_output_created_when_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case(tmp_path / "cases", "new")
    install(monkeypatch, [ChangeAction.NO_PATCH])
    output = tmp_path / "new-output"
    run_advanced_benchmark((case,), output)
    assert output.is_dir()


@pytest.mark.parametrize("kind", ["nonempty", "file", "symlink"])
def test_invalid_existing_output_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    case = make_case(tmp_path / "cases", "case")
    monkeypatch.setattr(harness, "validate_case", lambda case: None)
    output = tmp_path / "output"
    if kind == "nonempty": output.mkdir(); (output / "x").write_text("x")
    elif kind == "file": output.write_text("x")
    else:
        target = tmp_path / "target"; target.mkdir(); output.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError): run_advanced_benchmark((case,), output)


@pytest.mark.parametrize("relation", ["equal", "inside", "contains"])
def test_output_case_overlap_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relation: str) -> None:
    case = make_case(tmp_path / "cases", "case")
    monkeypatch.setattr(harness, "validate_case", lambda case: None)
    output = case if relation == "equal" else (case / "output" if relation == "inside" else tmp_path)
    with pytest.raises(ValueError, match="disjoint"): run_advanced_benchmark((case,), output)


def test_duplicate_case_names_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = make_case(tmp_path / "a", "same"); second = make_case(tmp_path / "b", "same")
    monkeypatch.setattr(harness, "validate_case", lambda case: None)
    with pytest.raises(ValueError, match="unique"): run_advanced_benchmark((first, second), tmp_path / "output")


@pytest.mark.parametrize("cases", [[], (), ("not-path",)])
def test_invalid_case_dirs_rejected(tmp_path: Path, cases) -> None:
    with pytest.raises(ValueError): run_advanced_benchmark(cases, tmp_path / "output")


def test_wrong_output_type_and_blank_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case(tmp_path / "cases", "case"); monkeypatch.setattr(harness, "validate_case", lambda case: None)
    with pytest.raises(ValueError, match="output_dir"): run_advanced_benchmark((case,), "output")
    with pytest.raises(ValueError, match="model"): run_advanced_benchmark((case,), tmp_path / "output", model=" ")


@pytest.mark.parametrize("field", ["extraction_timeout_seconds", "patch_timeout_seconds", "hidden_timeout_seconds"])
@pytest.mark.parametrize("value", [0, -1, True, math.inf, math.nan, "30"])
def test_invalid_timeouts_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value) -> None:
    case = make_case(tmp_path / "cases", "case"); monkeypatch.setattr(harness, "validate_case", lambda case: None)
    with pytest.raises(ValueError, match="positive finite"): run_advanced_benchmark((case,), tmp_path / "output", **{field: value})


def case_value(tmp_path: Path, *, success=True, patch=False) -> AdvancedCaseRun:
    eval_value = evaluation("case", success)
    extraction = codex(tmp_path / "extract")
    patch_run = codex(tmp_path / "patch", duration=2.0) if patch else None
    action = ChangeAction.PATCH if patch else ChangeAction.NO_PATCH
    solver = validate_solver_result({"schema_version": 1, "action": action.value,
        "changed_files": ["rule.py"] if patch else [], "evidence_ids": ["SOURCE"],
        "human_review_required": patch, "summary": "summary"}) if success else None
    return AdvancedCaseRun("case", action, success, None if success else "failed",
        2 if patch else 1, 3.0 if patch else 1.0, extraction, patch_run, solver,
        eval_value, tmp_path / "workspace", tmp_path / "evaluation", tmp_path / "workflow")


@pytest.mark.parametrize("name,value", [
    ("case_id", " "), ("action", "PATCH"), ("workflow_completed_successfully", 1),
    ("workflow_error", " "), ("codex_call_count", True),
    ("total_codex_duration_seconds", math.inf), ("extraction_codex_run", object()),
    ("patch_codex_run", object()), ("solver_result", object()),
    ("evaluation", object()), ("workspace_snapshot", "path"),
])
def test_advanced_case_validation(tmp_path: Path, name: str, value) -> None:
    good = case_value(tmp_path); kwargs = {f.name: getattr(good, f.name) for f in fields(good)}; kwargs[name] = value
    with pytest.raises(ValueError): AdvancedCaseRun(**kwargs)


def test_advanced_case_consistency_and_immutability(tmp_path: Path) -> None:
    good = case_value(tmp_path)
    kwargs = {f.name: getattr(good, f.name) for f in fields(good)}
    kwargs["codex_call_count"] = 2
    with pytest.raises(ValueError, match="agree"): AdvancedCaseRun(**kwargs)
    with pytest.raises(FrozenInstanceError): good.case_id = "other"  # type: ignore[misc]


def benchmark_value(tmp_path: Path) -> AdvancedBenchmarkRun:
    case = case_value(tmp_path); aggregate = aggregate_case_evaluations((case.evaluation,))
    return AdvancedBenchmarkRun("model", "a"*64, "b"*64, (case,), aggregate,
        tmp_path, tmp_path / "metadata", tmp_path / "summary")


@pytest.mark.parametrize("name,value", [("model", " "), ("contract_prompt_sha256", "bad"),
    ("patch_prompt_sha256", "A"*64), ("cases", ()), ("evaluation", object()),
    ("output_dir", "path")])
def test_advanced_benchmark_validation(tmp_path: Path, name: str, value) -> None:
    good = benchmark_value(tmp_path); kwargs = {f.name: getattr(good, f.name) for f in fields(good)}; kwargs[name] = value
    with pytest.raises(ValueError): AdvancedBenchmarkRun(**kwargs)


def test_benchmark_consistency_properties_and_immutability(tmp_path: Path) -> None:
    first = case_value(tmp_path / "one")
    second_base = case_value(tmp_path / "two", success=False, patch=True)
    second = AdvancedCaseRun("other", second_base.action, False, "failed", 2, 3.0,
        second_base.extraction_codex_run, second_base.patch_codex_run, None,
        evaluation("other", False), second_base.workspace_snapshot,
        second_base.evaluation_path, second_base.workflow_metadata_path)
    aggregate = aggregate_case_evaluations((first.evaluation, second.evaluation))
    run = AdvancedBenchmarkRun("model", "a"*64, "b"*64, (first, second), aggregate,
        tmp_path, tmp_path / "metadata", tmp_path / "summary")
    assert run.total_codex_calls == 3 and run.total_codex_duration_seconds == 4.0
    assert run.workflow_failure_cases == ("other",)
    with pytest.raises(FrozenInstanceError): run.model = "other"  # type: ignore[misc]
    wrong = aggregate_case_evaluations((first.evaluation,))
    with pytest.raises(ValueError, match="match"): AdvancedBenchmarkRun("model", "a"*64, "b"*64, (first, second), wrong, tmp_path, tmp_path/"m", tmp_path/"s")


def test_harness_has_no_direct_solver_stage_or_case_specific_logic() -> None:
    source = Path(harness.__file__).read_text(encoding="utf-8").lower()
    assert "run_codex" not in source
    assert "run_contract_extraction(" not in source
    assert "run_authorized_patch(" not in source
    assert "case_01" not in source and "ground_truth[" not in source
    assert "baseline" not in source
