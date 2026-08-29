import hashlib
import json
import shutil
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

import evidencepatch.patch_runner as patch_runner
from evidencepatch.change_contract import ClinicalChangeContract
from evidencepatch.codex_runner import CodexRunResult
from evidencepatch.contract_extraction import CONTRACT_FILENAME, contract_from_mapping, contract_to_json
from evidencepatch.patch_runner import (
    AUTHORIZED_PATCH_PROMPT,
    AUTHORIZED_PATCH_PROMPT_SHA256,
    AuthorizedPatchRun,
    run_authorized_patch,
)
from evidencepatch.repo_diff import RepositoryDiff


def mapping(kind: str = "patch") -> dict[str, object]:
    change = kind == "patch"
    return {
        "schema_version": 1,
        "evidence": [{
            "evidence_id": "SYNTHETIC-SOURCE",
            "authority": "AUTHORITATIVE" if kind != "escalate" else "DRAFT",
            "status": "CURRENT" if kind != "escalate" else "PROVISIONAL",
            "proposes_executable_change": change or kind == "escalate",
            "conflicts_with_current_authority": False,
        }],
        "executable_behavior_change": change,
        "semantic_equivalence": kind == "no_patch",
        "unresolved_conflict": False,
        "ambiguous_or_incomplete": False,
        "rationale": "Generic source-grounded assessment.",
    }


def setup(tmp_path: Path, kind: str = "patch") -> tuple[Path, Path, ClinicalChangeContract]:
    workspace = tmp_path / "workspace"
    (workspace / "evidence").mkdir(parents=True)
    (workspace / "repo").mkdir()
    (workspace / "task.md").write_text("Maintain the software.\n", encoding="utf-8")
    (workspace / "evidence" / "source.md").write_text("Synthetic evidence.\n", encoding="utf-8")
    (workspace / "repo" / "rule.py").write_text("VALUE = 1\n", encoding="utf-8")
    contract = contract_from_mapping(mapping(kind))
    (workspace / CONTRACT_FILENAME).write_text(contract_to_json(contract), encoding="utf-8")
    canonical = tmp_path / "canonical"
    shutil.copytree(workspace / "repo", canonical)
    return workspace, canonical, contract


def result(artifacts: Path, returncode=0, timed_out=False) -> CodexRunResult:
    return CodexRunResult("model", "codex test", returncode, timed_out, 0.1,
        artifacts / "events", artifacts / "stderr", artifacts / "prompt", artifacts / "metadata")


def fake(monkeypatch: pytest.MonkeyPatch, action=None, returncode=0, timed_out=False):
    calls = []
    def run(workspace, artifacts_dir, prompt, *, model, timeout_seconds):
        calls.append((workspace, artifacts_dir, prompt, model, timeout_seconds))
        if action:
            action(workspace)
        return result(artifacts_dir, returncode, timed_out)
    monkeypatch.setattr(patch_runner, "run_codex", run)
    return calls


def modify_repo(workspace: Path) -> None:
    (workspace / "repo" / "rule.py").write_text("VALUE = 2\n", encoding="utf-8")


def test_valid_patch_succeeds_with_expected_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical, contract = setup(tmp_path)
    fake(monkeypatch, modify_repo)
    run = run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert run.completed_successfully
    assert run.repository_diff.modified_files == ("rule.py",)
    assert run.error is None


def test_exact_prompt_and_arguments_forwarded_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical, contract = setup(tmp_path)
    calls = fake(monkeypatch)
    artifacts = tmp_path / "artifacts"
    run_authorized_patch(workspace, canonical, contract, artifacts, model="selected", timeout_seconds=12.5)
    assert calls == [(workspace.resolve(), artifacts, AUTHORIZED_PATCH_PROMPT, "selected", 12.5)]


def test_prompt_and_contract_hashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical, contract = setup(tmp_path)
    fake(monkeypatch)
    run = run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert AUTHORIZED_PATCH_PROMPT_SHA256 == hashlib.sha256(AUTHORIZED_PATCH_PROMPT.encode()).hexdigest()
    assert run.contract_sha256 == hashlib.sha256(contract_to_json(contract).encode()).hexdigest()


def test_workspace_contract_must_equal_argument(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical, contract = setup(tmp_path)
    other = contract_from_mapping({**mapping(), "rationale": "Different rationale."})
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="does not equal"):
        run_authorized_patch(workspace, canonical, other, tmp_path / "artifacts")
    assert not calls


def test_malformed_contract_rejected_before_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical, contract = setup(tmp_path)
    (workspace / CONTRACT_FILENAME).write_text("{bad", encoding="utf-8")
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="invalid contract JSON"):
        run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert not calls


@pytest.mark.parametrize("kind", ["no_patch", "escalate"])
def test_non_patch_authorization_rejected_without_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    workspace, canonical, contract = setup(tmp_path, kind)
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="PATCH contract"):
        run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert calls == []


def test_runner_uses_frozen_gate_instead_of_duplicate_logic() -> None:
    assert patch_runner.decide_change_action.__module__ == "evidencepatch.change_contract"


@pytest.mark.parametrize("name,is_dir", [("extra.txt", False), ("extra", True)])
def test_initial_extra_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, is_dir: bool) -> None:
    workspace, canonical, contract = setup(tmp_path)
    path = workspace / name
    path.mkdir() if is_dir else path.write_text("extra", encoding="utf-8")
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="exactly"):
        run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert not calls


@pytest.mark.parametrize("name", ["task.md", "evidence", "repo", CONTRACT_FILENAME])
def test_missing_required_entry_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    workspace, canonical, contract = setup(tmp_path)
    path = workspace / name
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="exactly"):
        run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert not calls


@pytest.mark.parametrize("name", ["evidence", "repo"])
def test_empty_directory_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    workspace, canonical, contract = setup(tmp_path)
    for path in (workspace / name).iterdir(): path.unlink()
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="at least one regular file"):
        run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert not calls


@pytest.mark.parametrize("name", ["task.md", "evidence", "repo", CONTRACT_FILENAME])
def test_required_symlink_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    workspace, canonical, contract = setup(tmp_path)
    path = workspace / name
    target = tmp_path / f"target-{name.replace('.', '-')}"
    path.rename(target)
    path.symlink_to(target, target_is_directory=target.is_dir())
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="symlink"):
        run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert not calls


@pytest.mark.parametrize("name", ["evidence", "repo"])
def test_nested_symlink_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    workspace, canonical, contract = setup(tmp_path)
    target = tmp_path / "outside"
    target.write_text("outside", encoding="utf-8")
    (workspace / name / "link").symlink_to(target)
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="symlinks"):
        run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert not calls


def test_canonical_must_initially_match_and_is_not_modified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical, contract = setup(tmp_path)
    original = (canonical / "rule.py").read_bytes()
    (workspace / "repo" / "rule.py").write_text("dirty", encoding="utf-8")
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="initially match"):
        run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert not calls and (canonical / "rule.py").read_bytes() == original


def test_canonical_equal_to_workspace_repo_rejected_before_codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, _, contract = setup(tmp_path)
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="canonical_repo must be outside"):
        run_authorized_patch(workspace, workspace / "repo", contract, tmp_path / "artifacts")
    assert calls == []


def test_canonical_inside_workspace_rejected_before_codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, _, contract = setup(tmp_path)
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="canonical_repo must be outside"):
        run_authorized_patch(workspace, workspace / "evidence", contract, tmp_path / "artifacts")
    assert calls == []


def test_workspace_inside_canonical_rejected_before_codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, _, contract = setup(tmp_path)
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="canonical_repo must be outside"):
        run_authorized_patch(workspace, tmp_path, contract, tmp_path / "artifacts")
    assert calls == []


@pytest.mark.parametrize("relationship", ["inside", "equal", "contains"])
def test_artifacts_canonical_overlap_rejected_before_codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relationship: str) -> None:
    workspace, canonical, contract = setup(tmp_path)
    if relationship == "inside":
        artifacts = canonical / "artifacts"
    elif relationship == "equal":
        artifacts = canonical
    else:
        artifacts = tmp_path
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="artifacts_dir must be outside"):
        run_authorized_patch(workspace, canonical, contract, artifacts)
    assert calls == []


def test_wrong_artifacts_type_rejected_before_codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical, contract = setup(tmp_path)
    calls = fake(monkeypatch)
    with pytest.raises(ValueError, match="artifacts_dir must be a pathlib.Path"):
        run_authorized_patch(workspace, canonical, contract, "artifacts")  # type: ignore[arg-type]
    assert calls == []


def test_disjoint_layout_succeeds_and_preserves_canonical_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical, contract = setup(tmp_path)
    before = {path.relative_to(canonical): path.read_bytes() for path in canonical.rglob("*") if path.is_file()}
    calls = fake(monkeypatch, modify_repo)
    run = run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    after = {path.relative_to(canonical): path.read_bytes() for path in canonical.rglob("*") if path.is_file()}
    assert run.completed_successfully
    assert len(calls) == 1
    assert after == before


def test_protected_manifest_unchanged_on_valid_patch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical, contract = setup(tmp_path)
    fake(monkeypatch, modify_repo)
    run = run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert run.protected_inputs_unchanged
    assert run.protected_manifest_before == run.protected_manifest_after


def mutation(kind: str):
    def act(root: Path) -> None:
        evidence = root / "evidence"
        if kind == "task": (root / "task.md").write_text("changed", encoding="utf-8")
        elif kind == "evidence_modify": (evidence / "source.md").write_text("changed", encoding="utf-8")
        elif kind == "evidence_add": (evidence / "new.md").write_text("new", encoding="utf-8")
        elif kind == "evidence_delete": (evidence / "source.md").unlink()
        elif kind == "empty_add": (evidence / "empty").mkdir()
        elif kind == "directory_delete": (evidence / "existing-empty").rmdir()
        elif kind == "contract": (root / CONTRACT_FILENAME).write_text("changed", encoding="utf-8")
    return act


@pytest.mark.parametrize("kind", ["task", "evidence_modify", "evidence_add", "evidence_delete", "empty_add", "directory_delete", "contract"])
def test_protected_mutation_is_structured_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    workspace, canonical, contract = setup(tmp_path)
    if kind == "directory_delete": (workspace / "evidence" / "existing-empty").mkdir()
    fake(monkeypatch, mutation(kind))
    run = run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert not run.completed_successfully
    assert run.repository_diff is None
    assert not run.protected_inputs_unchanged


def test_post_run_protected_symlink_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical, contract = setup(tmp_path)
    outside = tmp_path / "outside"; outside.write_text("x", encoding="utf-8")
    fake(monkeypatch, lambda root: (root / "evidence" / "link").symlink_to(outside))
    run = run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert run.repository_diff is None and run.protected_manifest_after is None
    assert "symlink" in run.error


@pytest.mark.parametrize("name,is_dir", [("notes.txt", False), ("notes", True), ("evidencepatch_result.json", False)])
def test_post_run_extra_root_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, is_dir: bool) -> None:
    workspace, canonical, contract = setup(tmp_path)
    def act(root: Path):
        path = root / name
        path.mkdir() if is_dir else path.write_text("extra", encoding="utf-8")
    fake(monkeypatch, act)
    run = run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert run.repository_diff is None and "disallowed root" in run.error


@pytest.mark.parametrize("returncode,timed_out", [(None, True), (3, False)])
@pytest.mark.parametrize("changes_repo", [False, True])
def test_failed_process_never_accepts_repo_and_records_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returncode, timed_out, changes_repo: bool) -> None:
    workspace, canonical, contract = setup(tmp_path)
    fake(monkeypatch, modify_repo if changes_repo else None, returncode, timed_out)
    run = run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert run.repository_diff is None and run.error
    assert run.protected_manifest_after == run.protected_manifest_before


@pytest.mark.parametrize("change,expected_bucket,expected_path", [
    (modify_repo, "modified_files", "rule.py"),
    (lambda root: (root / "repo" / "tests.py").write_text("test = True", encoding="utf-8"), "added_files", "tests.py"),
    (lambda root: (root / "repo" / "rule.py").unlink(), "deleted_files", "rule.py"),
])
def test_success_returns_frozen_repository_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change, expected_bucket: str, expected_path: str) -> None:
    workspace, canonical, contract = setup(tmp_path)
    fake(monkeypatch, change)
    run = run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert isinstance(run.repository_diff, RepositoryDiff)
    assert expected_path in getattr(run.repository_diff, expected_bucket)


def test_clean_diff_is_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical, contract = setup(tmp_path)
    fake(monkeypatch)
    run = run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert run.completed_successfully and run.repository_diff.is_clean


def test_unsafe_post_run_repo_symlink_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical, contract = setup(tmp_path)
    outside = tmp_path / "outside"; outside.write_text("x", encoding="utf-8")
    fake(monkeypatch, lambda root: (root / "repo" / "link").symlink_to(outside))
    run = run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert run.repository_diff is None and "symlink" in run.error


def test_errors_are_normalized_and_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, canonical, contract = setup(tmp_path)
    fake(monkeypatch)
    original = patch_runner.compare_repositories
    calls = 0
    def compare(a, b):
        nonlocal calls; calls += 1
        if calls == 1: return original(a, b)
        raise ValueError(("long \n text " * 100))
    monkeypatch.setattr(patch_runner, "compare_repositories", compare)
    run = run_authorized_patch(workspace, canonical, contract, tmp_path / "artifacts")
    assert len(run.error) == 500 and run.error.endswith("...")
    assert run.error == " ".join(run.error.split())


def valid_value(tmp_path: Path) -> AuthorizedPatchRun:
    digest = "a" * 64
    return AuthorizedPatchRun(result(tmp_path), RepositoryDiff((), (), ()), digest, digest, digest, digest, True, None)


@pytest.mark.parametrize("name,value", [
    ("codex_run", object()), ("repository_diff", object()),
    ("prompt_sha256", "bad"), ("contract_sha256", "A" * 64),
    ("protected_manifest_before", "bad"), ("protected_manifest_after", "z" * 64),
    ("protected_inputs_unchanged", 1), ("error", " "),
])
def test_result_field_validation(tmp_path: Path, name: str, value: object) -> None:
    good = valid_value(tmp_path)
    kwargs = {field.name: getattr(good, field.name) for field in fields(good)}
    kwargs[name] = value
    with pytest.raises(ValueError): AuthorizedPatchRun(**kwargs)


def test_result_logical_consistency_and_property(tmp_path: Path) -> None:
    good = valid_value(tmp_path)
    assert good.completed_successfully
    with pytest.raises(ValueError, match="failed patch run"):
        AuthorizedPatchRun(good.codex_run, None, good.prompt_sha256, good.contract_sha256, good.protected_manifest_before, good.protected_manifest_after, True, None)
    failed = AuthorizedPatchRun(result(tmp_path, 1), None, good.prompt_sha256, good.contract_sha256, good.protected_manifest_before, good.protected_manifest_after, True, "failed")
    assert not failed.completed_successfully


def test_dataclass_immutable(tmp_path: Path) -> None:
    with pytest.raises(FrozenInstanceError):
        valid_value(tmp_path).error = "changed"  # type: ignore[misc]


def test_prompt_policy_and_hygiene() -> None:
    prompt = AUTHORIZED_PATCH_PROMPT.lower()
    assert "do not reconsider" in prompt
    assert "do not create evidencepatch_result.json" in prompt
    assert "modify only files under repo/" in prompt
    assert "do not use the internet, web\nsearch, or external search" in prompt
    assert "case_" not in prompt
    assert "ground_truth.json" not in prompt
