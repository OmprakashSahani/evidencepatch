import json
import shutil
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

import evidencepatch.workflow as workflow
from evidencepatch.change_contract import ChangeAction, ClinicalChangeContract
from evidencepatch.codex_runner import CodexRunResult
from evidencepatch.contract_extraction import CONTRACT_FILENAME, contract_from_mapping, contract_to_json
from evidencepatch.contract_runner import ContractExtractionRun
from evidencepatch.patch_runner import AuthorizedPatchRun
from evidencepatch.repo_diff import RepositoryDiff, compare_repositories
from evidencepatch.result_contract import RESULT_FILENAME, load_solver_result
from evidencepatch.workflow import EvidencePatchWorkflowRun, run_evidencepatch_workflow


def contract(kind: str, evidence_ids=("SOURCE-A", "SOURCE-B")) -> ClinicalChangeContract:
    patch = kind == "PATCH"
    escalate = kind == "ESCALATE"
    return contract_from_mapping({
        "schema_version": 1,
        "evidence": [{
            "evidence_id": evidence_id,
            "authority": "DRAFT" if escalate else "AUTHORITATIVE",
            "status": "PROVISIONAL" if escalate else "CURRENT",
            "proposes_executable_change": patch or escalate,
            "conflicts_with_current_authority": False,
        } for evidence_id in evidence_ids],
        "executable_behavior_change": patch,
        "semantic_equivalence": kind == "NO_PATCH",
        "unresolved_conflict": False,
        "ambiguous_or_incomplete": False,
        "rationale": "The supplied sources establish the structured evidence state.",
    })


def setup(tmp_path: Path):
    workspace = tmp_path / "workspace"
    (workspace / "evidence").mkdir(parents=True)
    (workspace / "repo").mkdir()
    (workspace / "task.md").write_text("Assess and maintain.\n", encoding="utf-8")
    (workspace / "evidence" / "source.md").write_text("Synthetic evidence.\n", encoding="utf-8")
    (workspace / "repo" / "rule.py").write_text("VALUE = 1\n", encoding="utf-8")
    canonical = tmp_path / "canonical"
    shutil.copytree(workspace / "repo", canonical)
    return workspace, canonical


def codex(artifacts: Path, *, duration=1.0, returncode=0) -> CodexRunResult:
    return CodexRunResult("model", "codex test", returncode, False, duration,
        artifacts / "events", artifacts / "stderr", artifacts / "prompt", artifacts / "metadata")


def extraction_value(workspace: Path, artifacts: Path, value: ClinicalChangeContract, *, ok=True, duration=1.0) -> ContractExtractionRun:
    digest = "a" * 64
    if ok:
        (workspace / CONTRACT_FILENAME).write_text(contract_to_json(value), encoding="utf-8")
        return ContractExtractionRun(codex(artifacts, duration=duration), value,
            workspace / CONTRACT_FILENAME, digest, digest, digest, True, None)
    return ContractExtractionRun(codex(artifacts, duration=duration, returncode=1), None,
        workspace / CONTRACT_FILENAME, digest, digest, digest, True, " extraction   failed ".strip())


def patch_value(workspace: Path, canonical: Path, artifacts: Path, *, mode="modify", ok=True, duration=2.0) -> AuthorizedPatchRun:
    if mode == "modify":
        (workspace / "repo" / "rule.py").write_text("VALUE = 2\n", encoding="utf-8")
    elif mode == "multi":
        (workspace / "repo" / "rule.py").write_text("VALUE = 2\n", encoding="utf-8")
        (workspace / "repo" / "test_rule.py").write_text("assert True\n", encoding="utf-8")
        (workspace / "repo" / "old.py").unlink()
    diff = compare_repositories(canonical, workspace / "repo")
    digest = "b" * 64
    if ok:
        return AuthorizedPatchRun(codex(artifacts, duration=duration), diff,
            digest, digest, digest, digest, True, None)
    return AuthorizedPatchRun(codex(artifacts, duration=duration, returncode=1), None,
        digest, digest, digest, digest, True, "patch failed")


def install(monkeypatch: pytest.MonkeyPatch, workspace: Path, canonical: Path, value: ClinicalChangeContract,
            *, extraction_ok=True, patch_ok=True, patch_mode="modify", extraction_hook=None, patch_hook=None):
    extraction_calls = []
    patch_calls = []
    def extract(ws, artifacts, *, model, timeout_seconds):
        extraction_calls.append((ws, artifacts, model, timeout_seconds))
        if extraction_hook: extraction_hook(ws)
        return extraction_value(ws, artifacts, value, ok=extraction_ok)
    def patch(ws, canon, supplied, artifacts, *, model, timeout_seconds):
        patch_calls.append((ws, canon, supplied, artifacts, model, timeout_seconds))
        if patch_hook: patch_hook(ws)
        return patch_value(ws, canon, artifacts, mode=patch_mode, ok=patch_ok)
    monkeypatch.setattr(workflow, "run_contract_extraction", extract)
    monkeypatch.setattr(workflow, "run_authorized_patch", patch)
    return extraction_calls, patch_calls


@pytest.mark.parametrize("kind,expected_calls", [("NO_PATCH", 1), ("ESCALATE", 1), ("PATCH", 2)])
def test_successful_workflow_branches_and_call_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, expected_calls: int) -> None:
    workspace, canonical = setup(tmp_path)
    value = contract(kind)
    extraction_calls, patch_calls = install(monkeypatch, workspace, canonical, value)
    run = run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert run.completed_successfully and run.action.value == kind
    assert run.codex_call_count == expected_calls
    assert len(extraction_calls) == 1
    assert len(patch_calls) == (1 if kind == "PATCH" else 0)
    assert run.solver_result.action == kind


def test_model_timeouts_and_artifacts_forwarded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical = setup(tmp_path); value = contract("PATCH")
    extraction_calls, patch_calls = install(monkeypatch, workspace, canonical, value)
    extract_artifacts, patch_artifacts = tmp_path / "extract", tmp_path / "patch"
    run_evidencepatch_workflow(workspace, canonical, extract_artifacts, patch_artifacts,
        model="chosen", extraction_timeout_seconds=11, patch_timeout_seconds=22)
    assert extraction_calls == [(workspace.resolve(), extract_artifacts, "chosen", 11)]
    assert patch_calls[0][3:] == (patch_artifacts, "chosen", 22)


def test_extraction_failure_is_structured_without_patch_or_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical = setup(tmp_path); value = contract("PATCH")
    extraction_calls, patch_calls = install(monkeypatch, workspace, canonical, value, extraction_ok=False)
    run = run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert not run.completed_successfully and run.action is None and run.solver_result is None
    assert len(extraction_calls) == 1 and patch_calls == []
    assert not (workspace / RESULT_FILENAME).exists()


def test_frozen_governance_and_review_helpers_are_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical = setup(tmp_path); value = contract("NO_PATCH")
    install(monkeypatch, workspace, canonical, value)
    decisions = []; reviews = []
    real_decide, real_review = workflow.decide_change_action, workflow.requires_human_review
    monkeypatch.setattr(workflow, "decide_change_action", lambda item: decisions.append(item) or real_decide(item))
    monkeypatch.setattr(workflow, "requires_human_review", lambda action: reviews.append(action) or real_review(action))
    run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert decisions == [value] and reviews == [ChangeAction.NO_PATCH]


@pytest.mark.parametrize("kind,review", [("NO_PATCH", False), ("ESCALATE", True), ("PATCH", True)])
def test_result_fields_provenance_summary_and_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, review: bool) -> None:
    workspace, canonical = setup(tmp_path); value = contract(kind, ("SECOND", "FIRST"))
    install(monkeypatch, workspace, canonical, value)
    run = run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert run.solver_result.evidence_ids == ("SECOND", "FIRST")
    assert run.solver_result.summary == f"{kind}: {value.rationale}"
    assert run.solver_result.human_review_required is review
    if kind != "PATCH": assert run.solver_result.changed_files == ()


def test_patch_changed_files_exactly_follow_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical = setup(tmp_path); value = contract("PATCH")
    (workspace / "repo" / "old.py").write_text("old\n", encoding="utf-8")
    shutil.copy2(workspace / "repo" / "old.py", canonical / "old.py")
    install(monkeypatch, workspace, canonical, value, patch_mode="multi")
    run = run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert run.solver_result.changed_files == run.patch_run.repository_diff.changed_files
    assert run.solver_result.changed_files == ("old.py", "rule.py", "test_rule.py")


@pytest.mark.parametrize("kind", ["NO_PATCH", "ESCALATE"])
def test_nonpatch_repo_mutation_fails_without_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    workspace, canonical = setup(tmp_path); value = contract(kind)
    install(monkeypatch, workspace, canonical, value,
        extraction_hook=lambda ws: (ws / "repo" / "rule.py").write_text("dirty", encoding="utf-8"))
    run = run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert not run.completed_successfully and run.action.value == kind
    assert not (workspace / RESULT_FILENAME).exists()


def test_failed_patch_is_not_rewritten_and_creates_no_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical = setup(tmp_path); value = contract("PATCH")
    _, patch_calls = install(monkeypatch, workspace, canonical, value, patch_ok=False)
    run = run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert not run.completed_successfully and run.action is ChangeAction.PATCH
    assert run.patch_run is not None and len(patch_calls) == 1
    assert not (workspace / RESULT_FILENAME).exists()


def test_clean_patch_fails_without_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical = setup(tmp_path); value = contract("PATCH")
    install(monkeypatch, workspace, canonical, value, patch_mode="clean")
    run = run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert not run.completed_successfully and "no repository changes" in run.error
    assert not (workspace / RESULT_FILENAME).exists()


def test_mapping_uses_validator_and_result_round_trips_deterministically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical = setup(tmp_path); value = contract("NO_PATCH")
    install(monkeypatch, workspace, canonical, value)
    seen = []
    real_validate = workflow.validate_solver_result
    monkeypatch.setattr(workflow, "validate_solver_result", lambda data: seen.append(data.copy()) or real_validate(data))
    run = run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert len(seen) == 1 and load_solver_result(run.result_path) == run.solver_result
    assert run.result_path.read_text(encoding="utf-8") == json.dumps(seen[0], indent=2, sort_keys=True) + "\n"


@pytest.mark.parametrize("symlink", [False, True])
def test_preexisting_result_rejected_before_extraction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, symlink: bool) -> None:
    workspace, canonical = setup(tmp_path); value = contract("NO_PATCH")
    path = workspace / RESULT_FILENAME
    if symlink:
        target = tmp_path / "target"; target.write_text("x", encoding="utf-8"); path.symlink_to(target)
    else: path.write_text("do not overwrite", encoding="utf-8")
    extraction_calls, _ = install(monkeypatch, workspace, canonical, value)
    with pytest.raises(ValueError, match="must not already exist"):
        run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert extraction_calls == []
    assert path.exists()


def test_successful_final_layout_exact_and_contract_remains(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical = setup(tmp_path); value = contract("NO_PATCH")
    install(monkeypatch, workspace, canonical, value)
    run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert {path.name for path in workspace.iterdir()} == {"task.md", "evidence", "repo", CONTRACT_FILENAME, RESULT_FILENAME}
    assert (workspace / CONTRACT_FILENAME).exists()


@pytest.mark.parametrize("is_dir", [False, True])
def test_extra_final_root_fails_removes_only_result_and_keeps_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, is_dir: bool) -> None:
    workspace, canonical = setup(tmp_path); value = contract("PATCH")
    def extra(ws: Path):
        path = ws / "extra"
        path.mkdir() if is_dir else path.write_text("keep", encoding="utf-8")
    install(monkeypatch, workspace, canonical, value, patch_hook=extra)
    run = run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert not run.completed_successfully
    assert not (workspace / RESULT_FILENAME).exists()
    assert (workspace / "extra").exists() and (workspace / CONTRACT_FILENAME).exists()
    assert (workspace / "repo" / "rule.py").read_text() == "VALUE = 2\n"


def test_canonical_bytes_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical = setup(tmp_path); value = contract("PATCH")
    before = (canonical / "rule.py").read_bytes()
    install(monkeypatch, workspace, canonical, value)
    run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert (canonical / "rule.py").read_bytes() == before


@pytest.mark.parametrize("canonical_mode", ["equal", "contains"])
def test_workspace_canonical_overlap_rejected_before_extraction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, canonical_mode: str) -> None:
    workspace, canonical = setup(tmp_path); value = contract("NO_PATCH")
    canonical = workspace if canonical_mode == "equal" else tmp_path
    extraction_calls, _ = install(monkeypatch, workspace, canonical, value)
    with pytest.raises(ValueError, match="disjoint"):
        run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert extraction_calls == []


def test_initial_repo_mismatch_rejected_before_extraction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical = setup(tmp_path); value = contract("NO_PATCH")
    (workspace / "repo" / "rule.py").write_text("dirty", encoding="utf-8")
    extraction_calls, _ = install(monkeypatch, workspace, canonical, value)
    with pytest.raises(ValueError, match="initially match"):
        run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert extraction_calls == []


@pytest.mark.parametrize("argument", ["workspace", "canonical_repo", "extraction_artifacts_dir", "patch_artifacts_dir"])
def test_wrong_path_types_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argument: str) -> None:
    workspace, canonical = setup(tmp_path); value = contract("NO_PATCH")
    install(monkeypatch, workspace, canonical, value)
    kwargs = dict(workspace=workspace, canonical_repo=canonical,
        extraction_artifacts_dir=tmp_path / "extract", patch_artifacts_dir=tmp_path / "patch")
    kwargs[argument] = "wrong"
    with pytest.raises(ValueError, match="pathlib.Path"):
        run_evidencepatch_workflow(**kwargs)


@pytest.mark.parametrize("artifact,relationship", [
    ("extraction", "equal_workspace"),
    ("extraction", "inside_workspace"),
    ("extraction", "contains_workspace"),
    ("extraction", "equal_canonical"),
    ("extraction", "inside_canonical"),
    ("extraction", "contains_canonical"),
    ("patch", "equal_workspace"),
    ("patch", "inside_workspace"),
    ("patch", "contains_workspace"),
    ("patch", "equal_canonical"),
    ("patch", "inside_canonical"),
    ("patch", "contains_canonical"),
])
def test_artifact_workspace_or_canonical_overlap_fails_before_extraction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact: str,
    relationship: str,
) -> None:
    workspace, canonical = setup(tmp_path)
    value = contract("NO_PATCH")
    extraction_calls, patch_calls = install(monkeypatch, workspace, canonical, value)
    paths = {
        "extraction_artifacts_dir": tmp_path / "extract",
        "patch_artifacts_dir": tmp_path / "patch",
    }
    subject = workspace if "workspace" in relationship else canonical
    if relationship.startswith("equal"):
        invalid = subject
    elif relationship.startswith("inside"):
        invalid = subject / "artifacts"
    else:
        invalid = tmp_path
    paths[f"{artifact}_artifacts_dir"] = invalid
    with pytest.raises(ValueError, match="outside and disjoint"):
        run_evidencepatch_workflow(workspace, canonical, **paths)
    assert extraction_calls == []
    assert patch_calls == []


@pytest.mark.parametrize("relationship", ["equal", "extraction_inside_patch", "patch_inside_extraction"])
def test_artifact_locations_cannot_overlap_each_other_before_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relationship: str
) -> None:
    workspace, canonical = setup(tmp_path)
    value = contract("PATCH")
    extraction_calls, patch_calls = install(monkeypatch, workspace, canonical, value)
    parent = tmp_path / "artifacts"
    if relationship == "equal":
        extraction, patch = parent, parent
    elif relationship == "extraction_inside_patch":
        extraction, patch = parent / "extract", parent
    else:
        extraction, patch = parent, parent / "patch"
    with pytest.raises(ValueError, match="outside and disjoint"):
        run_evidencepatch_workflow(workspace, canonical, extraction, patch)
    assert extraction_calls == []
    assert patch_calls == []


@pytest.mark.parametrize("artifact", ["extraction", "patch"])
def test_existing_artifact_symlink_rejected_before_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact: str
) -> None:
    workspace, canonical = setup(tmp_path)
    value = contract("PATCH")
    extraction_calls, patch_calls = install(monkeypatch, workspace, canonical, value)
    target = tmp_path / f"{artifact}-target"
    target.mkdir()
    link = tmp_path / f"{artifact}-link"
    link.symlink_to(target, target_is_directory=True)
    extraction = link if artifact == "extraction" else tmp_path / "extract"
    patch = link if artifact == "patch" else tmp_path / "patch"
    with pytest.raises(ValueError, match="must not be a symlink"):
        run_evidencepatch_workflow(workspace, canonical, extraction, patch)
    assert extraction_calls == []
    assert patch_calls == []


@pytest.mark.parametrize("kind", ["NO_PATCH", "ESCALATE", "PATCH"])
def test_disjoint_artifacts_preserve_branch_behavior_and_canonical_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    workspace, canonical = setup(tmp_path)
    value = contract(kind)
    before = (canonical / "rule.py").read_bytes()
    extraction_calls, patch_calls = install(monkeypatch, workspace, canonical, value)
    patch_artifacts = tmp_path / "patch-artifacts"
    run = run_evidencepatch_workflow(
        workspace, canonical, tmp_path / "extraction-artifacts", patch_artifacts
    )
    assert run.completed_successfully
    assert len(extraction_calls) == 1
    assert len(patch_calls) == (1 if kind == "PATCH" else 0)
    if kind != "PATCH":
        assert not patch_artifacts.exists()
    assert (canonical / "rule.py").read_bytes() == before


def test_error_is_normalized_and_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical = setup(tmp_path); value = contract("PATCH")
    install(monkeypatch, workspace, canonical, value, patch_ok=False)
    monkeypatch.setattr(workflow, "run_authorized_patch", lambda *args, **kwargs:
        AuthorizedPatchRun(codex(tmp_path, returncode=1), None, "b"*64, "b"*64, "b"*64, "b"*64, True, ("long \n text " * 100).strip()))
    run = run_evidencepatch_workflow(workspace, canonical, tmp_path / "extract", tmp_path / "patch")
    assert len(run.error) == 500 and run.error.endswith("...")
    assert run.error == " ".join(run.error.split())


def successful_value(tmp_path: Path) -> EvidencePatchWorkflowRun:
    workspace, canonical = setup(tmp_path); value = contract("NO_PATCH")
    extraction = extraction_value(workspace, tmp_path, value)
    solver = workflow.validate_solver_result({"schema_version": 1, "action": "NO_PATCH", "changed_files": [], "evidence_ids": ["SOURCE-A", "SOURCE-B"], "human_review_required": False, "summary": "NO_PATCH: rationale"})
    return EvidencePatchWorkflowRun(extraction, ChangeAction.NO_PATCH, None, solver, workspace / RESULT_FILENAME, None)


@pytest.mark.parametrize("name,value", [("extraction_run", object()), ("action", "PATCH"), ("patch_run", object()), ("solver_result", object()), ("result_path", "path"), ("error", " ")])
def test_result_field_validation(tmp_path: Path, name: str, value: object) -> None:
    good = successful_value(tmp_path)
    kwargs = {field.name: getattr(good, field.name) for field in fields(good)}; kwargs[name] = value
    with pytest.raises(ValueError): EvidencePatchWorkflowRun(**kwargs)


def test_result_logical_properties_and_immutability(tmp_path: Path) -> None:
    good = successful_value(tmp_path)
    assert good.completed_successfully and good.codex_call_count == 1
    assert good.total_codex_duration_seconds == 1.0
    with pytest.raises(ValueError, match="failed workflow"):
        EvidencePatchWorkflowRun(good.extraction_run, ChangeAction.NO_PATCH, None, None, good.result_path, None)
    with pytest.raises(FrozenInstanceError): good.error = "changed"  # type: ignore[misc]


def test_patch_duration_and_call_count(tmp_path: Path) -> None:
    workspace, canonical = setup(tmp_path); value = contract("PATCH")
    extraction = extraction_value(workspace, tmp_path / "extract", value, duration=1.25)
    patch = patch_value(workspace, canonical, tmp_path / "patch", duration=2.5)
    solver = workflow.validate_solver_result({"schema_version": 1, "action": "PATCH", "changed_files": ["rule.py"], "evidence_ids": ["SOURCE-A", "SOURCE-B"], "human_review_required": True, "summary": "PATCH: rationale"})
    run = EvidencePatchWorkflowRun(extraction, ChangeAction.PATCH, patch, solver, workspace / RESULT_FILENAME, None)
    assert run.codex_call_count == 2 and run.total_codex_duration_seconds == 3.75


def test_module_contains_no_benchmark_specific_decision_data() -> None:
    source = Path(workflow.__file__).read_text(encoding="utf-8").lower()
    assert "case_01" not in source and "ground_truth" not in source
