import hashlib
import json
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

import evidencepatch.contract_runner as runner
from evidencepatch.change_contract import ClinicalChangeContract
from evidencepatch.codex_runner import CodexRunResult
from evidencepatch.contract_extraction import (
    CONTRACT_EXTRACTION_PROMPT,
    CONTRACT_FILENAME,
    contract_from_mapping,
)
from evidencepatch.contract_runner import (
    CONTRACT_EXTRACTION_PROMPT_SHA256,
    ContractExtractionRun,
    run_contract_extraction,
)


def contract_mapping() -> dict[str, object]:
    return {
        "schema_version": 1,
        "evidence": [
            {
                "evidence_id": "SYNTHETIC-PUBLIC-SOURCE",
                "authority": "AUTHORITATIVE",
                "status": "CURRENT",
                "proposes_executable_change": True,
                "conflicts_with_current_authority": False,
            }
        ],
        "executable_behavior_change": True,
        "semantic_equivalence": False,
        "unresolved_conflict": False,
        "ambiguous_or_incomplete": False,
        "rationale": "The current source establishes an executable difference.",
    }


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "evidence").mkdir(parents=True)
    (workspace / "repo").mkdir()
    (workspace / "task.md").write_text("Assess the supplied material.\n", encoding="utf-8")
    (workspace / "evidence" / "source.md").write_text("Synthetic source.\n", encoding="utf-8")
    (workspace / "repo" / "rule.py").write_text("VALUE = 1\n", encoding="utf-8")
    return workspace


def codex_result(artifacts: Path, *, returncode: int | None = 0, timed_out: bool = False) -> CodexRunResult:
    return CodexRunResult(
        model="generic-model",
        codex_version="codex-cli test",
        returncode=returncode,
        timed_out=timed_out,
        duration_seconds=0.25,
        events_path=artifacts / "events.jsonl",
        stderr_path=artifacts / "stderr.txt",
        prompt_path=artifacts / "prompt.txt",
        metadata_path=artifacts / "run_metadata.json",
    )


def install_fake_codex(monkeypatch: pytest.MonkeyPatch, action=None, *, returncode=0, timed_out=False):
    calls: list[tuple[Path, Path, str, str, float]] = []

    def fake(workspace, artifacts_dir, prompt, *, model, timeout_seconds):
        calls.append((workspace, artifacts_dir, prompt, model, timeout_seconds))
        if action is None:
            (workspace / CONTRACT_FILENAME).write_text(json.dumps(contract_mapping()), encoding="utf-8")
        else:
            action(workspace)
        return codex_result(artifacts_dir, returncode=returncode, timed_out=timed_out)

    monkeypatch.setattr(runner, "run_codex", fake)
    return calls


def test_valid_extraction_succeeds_and_parses_expected_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = make_workspace(tmp_path)
    install_fake_codex(monkeypatch)
    result = run_contract_extraction(workspace, tmp_path / "artifacts")
    assert result.completed_successfully
    assert result.contract == contract_from_mapping(contract_mapping())
    assert result.error is None


def test_frozen_prompt_and_arguments_forwarded_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = make_workspace(tmp_path)
    calls = install_fake_codex(monkeypatch)
    artifacts = tmp_path / "artifacts"
    run_contract_extraction(workspace, artifacts, model="chosen-model", timeout_seconds=12.5)
    assert calls == [(workspace.resolve(), artifacts, CONTRACT_EXTRACTION_PROMPT, "chosen-model", 12.5)]


def test_prompt_hash_is_computed_from_frozen_prompt() -> None:
    assert CONTRACT_EXTRACTION_PROMPT_SHA256 == hashlib.sha256(CONTRACT_EXTRACTION_PROMPT.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("extra_name,is_directory", [
    (CONTRACT_FILENAME, False),
    ("evidencepatch_result.json", False),
    ("notes.txt", False),
    ("extra", True),
])
def test_initial_extra_entry_rejected_before_codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra_name: str, is_directory: bool) -> None:
    workspace = make_workspace(tmp_path)
    extra = workspace / extra_name
    extra.mkdir() if is_directory else extra.write_text("extra", encoding="utf-8")
    calls = install_fake_codex(monkeypatch)
    with pytest.raises(ValueError, match="exactly"):
        run_contract_extraction(workspace, tmp_path / "artifacts")
    assert calls == []


@pytest.mark.parametrize("missing", ["task.md", "evidence", "repo"])
def test_missing_required_input_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    workspace = make_workspace(tmp_path)
    path = workspace / missing
    if path.is_dir():
        for child in path.iterdir():
            child.unlink()
        path.rmdir()
    else:
        path.unlink()
    calls = install_fake_codex(monkeypatch)
    with pytest.raises(ValueError, match="exactly"):
        run_contract_extraction(workspace, tmp_path / "artifacts")
    assert not calls


@pytest.mark.parametrize("empty", ["evidence", "repo"])
def test_empty_public_directory_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, empty: str) -> None:
    workspace = make_workspace(tmp_path)
    for child in (workspace / empty).iterdir():
        child.unlink()
    calls = install_fake_codex(monkeypatch)
    with pytest.raises(ValueError, match="at least one regular file"):
        run_contract_extraction(workspace, tmp_path / "artifacts")
    assert not calls


@pytest.mark.parametrize("target", ["task.md", "evidence", "repo"])
def test_required_input_symlink_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    workspace = make_workspace(tmp_path)
    path = workspace / target
    replacement = tmp_path / f"real-{target.replace('.', '-') }"
    path.rename(replacement)
    path.symlink_to(replacement, target_is_directory=replacement.is_dir())
    calls = install_fake_codex(monkeypatch)
    with pytest.raises(ValueError, match="symlink"):
        run_contract_extraction(workspace, tmp_path / "artifacts")
    assert not calls


@pytest.mark.parametrize("tree", ["evidence", "repo"])
def test_nested_public_symlink_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tree: str) -> None:
    workspace = make_workspace(tmp_path)
    external = tmp_path / "external.txt"
    external.write_text("private", encoding="utf-8")
    (workspace / tree / "link").symlink_to(external)
    calls = install_fake_codex(monkeypatch)
    with pytest.raises(ValueError, match="symlinks"):
        run_contract_extraction(workspace, tmp_path / "artifacts")
    assert not calls


def test_success_preserves_identical_public_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = make_workspace(tmp_path)
    install_fake_codex(monkeypatch)
    result = run_contract_extraction(workspace, tmp_path / "artifacts")
    assert result.public_inputs_unchanged is True
    assert result.public_input_manifest_after == result.public_input_manifest_before


def mutation_action(kind: str):
    def mutate(workspace: Path) -> None:
        evidence_file = workspace / "evidence" / "source.md"
        repo_file = workspace / "repo" / "rule.py"
        if kind == "task_modified":
            (workspace / "task.md").write_text("changed", encoding="utf-8")
        elif kind == "evidence_modified":
            evidence_file.write_text("changed", encoding="utf-8")
        elif kind == "repo_modified":
            repo_file.write_text("changed", encoding="utf-8")
        elif kind == "file_added":
            (workspace / "repo" / "added.py").write_text("new", encoding="utf-8")
        elif kind == "file_deleted":
            repo_file.unlink()
        elif kind == "empty_dir_added":
            (workspace / "repo" / "empty").mkdir()
        elif kind == "directory_deleted":
            empty = workspace / "repo" / "existing-empty"
            empty.rmdir()
        (workspace / CONTRACT_FILENAME).write_text(json.dumps(contract_mapping()), encoding="utf-8")
    return mutate


@pytest.mark.parametrize("kind", ["task_modified", "evidence_modified", "repo_modified", "file_added", "file_deleted", "empty_dir_added", "directory_deleted"])
def test_public_input_mutation_fails_extraction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    workspace = make_workspace(tmp_path)
    if kind == "directory_deleted":
        (workspace / "repo" / "existing-empty").mkdir()
    install_fake_codex(monkeypatch, mutation_action(kind))
    result = run_contract_extraction(workspace, tmp_path / "artifacts")
    assert not result.completed_successfully
    assert result.contract is None
    assert result.public_inputs_unchanged is False
    assert "modified" in result.error


def test_post_run_public_symlink_is_structured_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = make_workspace(tmp_path)
    external = tmp_path / "external"
    external.write_text("outside", encoding="utf-8")
    def act(root: Path) -> None:
        (root / "repo" / "link").symlink_to(external)
        (root / CONTRACT_FILENAME).write_text(json.dumps(contract_mapping()), encoding="utf-8")
    install_fake_codex(monkeypatch, act)
    result = run_contract_extraction(workspace, tmp_path / "artifacts")
    assert not result.completed_successfully
    assert result.public_input_manifest_after is None
    assert "symlink" in result.error


@pytest.mark.parametrize("name,is_directory", [("notes.txt", False), ("notes", True), ("evidencepatch_result.json", False)])
def test_post_run_extra_root_entry_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, is_directory: bool) -> None:
    workspace = make_workspace(tmp_path)
    def act(root: Path) -> None:
        (root / CONTRACT_FILENAME).write_text(json.dumps(contract_mapping()), encoding="utf-8")
        extra = root / name
        extra.mkdir() if is_directory else extra.write_text("extra", encoding="utf-8")
    install_fake_codex(monkeypatch, act)
    result = run_contract_extraction(workspace, tmp_path / "artifacts")
    assert not result.completed_successfully
    assert "Post-run workspace" in result.error


def test_missing_contract_after_success_is_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = make_workspace(tmp_path)
    install_fake_codex(monkeypatch, lambda root: None)
    result = run_contract_extraction(workspace, tmp_path / "artifacts")
    assert result.contract is None
    assert CONTRACT_FILENAME in result.error


def test_contract_symlink_is_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = make_workspace(tmp_path)
    target = tmp_path / "contract.json"
    target.write_text(json.dumps(contract_mapping()), encoding="utf-8")
    install_fake_codex(monkeypatch, lambda root: (root / CONTRACT_FILENAME).symlink_to(target))
    result = run_contract_extraction(workspace, tmp_path / "artifacts")
    assert result.contract is None
    assert "symbolic link" in result.error


@pytest.mark.parametrize("payload", ["{bad", json.dumps({"schema_version": 1}), json.dumps({**contract_mapping(), "semantic_equivalence": True})])
def test_invalid_contract_output_is_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str) -> None:
    workspace = make_workspace(tmp_path)
    install_fake_codex(monkeypatch, lambda root: (root / CONTRACT_FILENAME).write_text(payload, encoding="utf-8"))
    result = run_contract_extraction(workspace, tmp_path / "artifacts")
    assert result.contract is None
    assert result.error.startswith("Contract artifact was invalid:")


@pytest.mark.parametrize("returncode,timed_out", [(None, True), (2, False)])
@pytest.mark.parametrize("writes_contract", [False, True])
def test_failed_process_never_accepts_contract_and_records_safe_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returncode, timed_out, writes_contract: bool) -> None:
    workspace = make_workspace(tmp_path)
    action = None if writes_contract else (lambda root: None)
    install_fake_codex(monkeypatch, action, returncode=returncode, timed_out=timed_out)
    result = run_contract_extraction(workspace, tmp_path / "artifacts")
    assert result.contract is None
    assert result.error
    assert result.public_input_manifest_after == result.public_input_manifest_before
    assert result.public_inputs_unchanged


def test_error_diagnostic_is_normalized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = make_workspace(tmp_path)
    install_fake_codex(monkeypatch, lambda root: None)
    result = run_contract_extraction(workspace, tmp_path / "artifacts")
    assert result.error == " ".join(result.error.split())


def test_error_diagnostic_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = make_workspace(tmp_path)
    install_fake_codex(monkeypatch)
    monkeypatch.setattr(runner, "load_contract", lambda path: (_ for _ in ()).throw(ValueError("x" * 2000)))
    result = run_contract_extraction(workspace, tmp_path / "artifacts")
    assert len(result.error) == 500
    assert result.error.endswith("...")


def valid_run_value(tmp_path: Path) -> ContractExtractionRun:
    contract = contract_from_mapping(contract_mapping())
    codex = codex_result(tmp_path)
    digest = "a" * 64
    return ContractExtractionRun(codex, contract, tmp_path / CONTRACT_FILENAME, digest, digest, digest, True, None)


@pytest.mark.parametrize("field_name,bad_value", [
    ("codex_run", object()),
    ("contract", object()),
    ("contract_path", "path"),
    ("prompt_sha256", "A" * 64),
    ("public_input_manifest_before", "short"),
    ("public_input_manifest_after", "g" * 64),
    ("public_inputs_unchanged", 1),
    ("error", " "),
])
def test_result_validates_wrong_field_types(tmp_path: Path, field_name: str, bad_value: object) -> None:
    value = valid_run_value(tmp_path)
    kwargs = {field.name: getattr(value, field.name) for field in fields(value)}
    kwargs[field_name] = bad_value
    with pytest.raises(ValueError):
        ContractExtractionRun(**kwargs)


def test_failed_result_requires_none_contract_and_error(tmp_path: Path) -> None:
    value = valid_run_value(tmp_path)
    with pytest.raises(ValueError, match="failed extraction"):
        ContractExtractionRun(value.codex_run, None, value.contract_path, value.prompt_sha256, value.public_input_manifest_before, value.public_input_manifest_after, True, None)
    failed_codex = codex_result(tmp_path, returncode=1)
    with pytest.raises(ValueError, match="failed extraction"):
        ContractExtractionRun(failed_codex, value.contract, value.contract_path, value.prompt_sha256, value.public_input_manifest_before, value.public_input_manifest_after, True, None)


def test_completed_successfully_property_is_exact(tmp_path: Path) -> None:
    success = valid_run_value(tmp_path)
    failed = ContractExtractionRun(codex_result(tmp_path, returncode=1), None, success.contract_path, success.prompt_sha256, success.public_input_manifest_before, success.public_input_manifest_after, True, "process failed")
    assert success.completed_successfully is True
    assert failed.completed_successfully is False


def test_result_dataclass_is_immutable(tmp_path: Path) -> None:
    with pytest.raises(FrozenInstanceError):
        valid_run_value(tmp_path).error = "changed"  # type: ignore[misc]


def test_runner_has_no_final_action_field_or_gate_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = make_workspace(tmp_path)
    install_fake_codex(monkeypatch)
    result = run_contract_extraction(workspace, tmp_path / "artifacts")
    assert result.contract is not None
    assert "action" not in {field.name for field in fields(result)}
    assert not hasattr(runner, "decide_change_action")
