"""Authorized one-call execution boundary for repository patching."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re

from evidencepatch.change_contract import (
    ChangeAction,
    ClinicalChangeContract,
    decide_change_action,
)
from evidencepatch.codex_runner import CodexRunResult, run_codex
from evidencepatch.contract_extraction import (
    CONTRACT_FILENAME,
    contract_to_json,
    load_contract,
)
from evidencepatch.repo_diff import RepositoryDiff, compare_repositories


AUTHORIZED_PATCH_PROMPT = """You are the authorized implementation agent for a clinical-software maintenance task.

Work only inside the supplied workspace. Do not access files outside it,
hidden evaluation data, or evaluator code. Do not use the internet, web
search, or external search.

The Clinical Change Contract has already passed strict validation, and a
deterministic governance gate has already authorized PATCH. Do not reconsider
or replace the final governance action. The contract describes evidence
authority and executable semantic state; also consult the supplied source
evidence and current repository when implementing the authorized change.

Read task.md, every supplied evidence file, evidencepatch_contract.json, and
the current repo/. Modify only files under repo/. Implement the smallest
executable software change supported by the validated contract and controlling
evidence. Preserve unrelated behavior and existing safety invariants. Modify
or add visible tests under repo/tests/ when appropriate, and run relevant
visible repository tests when practical.

Do not create or modify root-level files. Do not modify task.md, evidence/, or
evidencepatch_contract.json. Do not create evidencepatch_result.json, another
contract, notes, or reports. Do not output a final PATCH, NO_PATCH, or ESCALATE
decision artifact.

If implementation cannot safely be completed, leave repo/ unchanged rather
than inventing unsupported behavior.
"""

AUTHORIZED_PATCH_PROMPT_SHA256 = hashlib.sha256(
    AUTHORIZED_PATCH_PROMPT.encode("utf-8")
).hexdigest()

_ROOT_ENTRIES = {"task.md", "evidence", "repo", CONTRACT_FILENAME}
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_ERROR_LIMIT = 500


@dataclass(frozen=True)
class AuthorizedPatchRun:
    """Process, integrity, and repository-diff result of an authorized patch."""

    codex_run: CodexRunResult
    repository_diff: RepositoryDiff | None
    prompt_sha256: str
    contract_sha256: str
    protected_manifest_before: str
    protected_manifest_after: str | None
    protected_inputs_unchanged: bool
    error: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.codex_run, CodexRunResult):
            raise ValueError("codex_run must be a CodexRunResult")
        if self.repository_diff is not None and not isinstance(
            self.repository_diff, RepositoryDiff
        ):
            raise ValueError("repository_diff must be a RepositoryDiff or None")
        for value, name in (
            (self.prompt_sha256, "prompt_sha256"),
            (self.contract_sha256, "contract_sha256"),
            (self.protected_manifest_before, "protected_manifest_before"),
        ):
            _validate_digest(value, name)
        if self.protected_manifest_after is not None:
            _validate_digest(
                self.protected_manifest_after, "protected_manifest_after"
            )
        if not isinstance(self.protected_inputs_unchanged, bool):
            raise ValueError("protected_inputs_unchanged must be a boolean")
        if self.error is not None and (
            not isinstance(self.error, str)
            or not self.error
            or self.error != self.error.strip()
        ):
            raise ValueError("error must be None or a non-empty stripped string")
        success = (
            self.codex_run.completed_successfully
            and self.repository_diff is not None
            and self.protected_inputs_unchanged
            and self.protected_manifest_after is not None
            and self.error is None
        )
        if not success and (self.repository_diff is not None or self.error is None):
            raise ValueError(
                "failed patch run must have repository_diff=None and a non-empty error"
            )

    @property
    def completed_successfully(self) -> bool:
        """Return whether execution, protection, and repository diff succeeded."""
        return (
            self.codex_run.completed_successfully
            and self.repository_diff is not None
            and self.protected_inputs_unchanged
            and self.protected_manifest_after is not None
            and self.error is None
        )


def _validate_digest(value: object, name: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{name} must be exactly 64 lowercase hexadecimal characters")


def _bounded_error(error: object) -> str:
    text = " ".join(str(error).split()) or "Unknown authorized patch failure"
    return text if len(text) <= _ERROR_LIMIT else text[: _ERROR_LIMIT - 3] + "..."


def _reject_symlinks(root: Path) -> None:
    for current, directories, files in os.walk(root, followlinks=False):
        base = Path(current)
        for name in (*directories, *files):
            path = base / name
            if path.is_symlink():
                raise ValueError(f"Workspace inputs must not contain symlinks: {path}")


def _validate_workspace(workspace: Path) -> Path:
    if not isinstance(workspace, Path):
        raise ValueError("workspace must be a pathlib.Path")
    if workspace.is_symlink():
        raise ValueError("workspace must not be a symlink")
    if not workspace.exists():
        raise FileNotFoundError(f"workspace does not exist: {workspace}")
    if not workspace.is_dir():
        raise ValueError(f"workspace is not a directory: {workspace}")
    entries = {path.name for path in workspace.iterdir()}
    if entries != _ROOT_ENTRIES:
        raise ValueError(
            "workspace must contain exactly task.md, evidence, repo, and "
            f"{CONTRACT_FILENAME}; found {sorted(entries)}"
        )
    task = workspace / "task.md"
    contract_path = workspace / CONTRACT_FILENAME
    if task.is_symlink() or not task.is_file():
        raise ValueError("task.md must be a non-symlink regular file")
    if contract_path.is_symlink() or not contract_path.is_file():
        raise ValueError(f"{CONTRACT_FILENAME} must be a non-symlink regular file")
    for name in ("evidence", "repo"):
        path = workspace / name
        if path.is_symlink() or not path.is_dir():
            raise ValueError(f"{name}/ must be a non-symlink directory")
        _reject_symlinks(path)
        if not any(item.is_file() for item in path.rglob("*")):
            raise ValueError(f"{name}/ must contain at least one regular file")
    return workspace.resolve()


def _validate_canonical_repo(canonical_repo: Path) -> Path:
    if not isinstance(canonical_repo, Path):
        raise ValueError("canonical_repo must be a pathlib.Path")
    if canonical_repo.is_symlink():
        raise ValueError("canonical_repo must not be a symlink")
    if not canonical_repo.exists():
        raise FileNotFoundError(f"canonical_repo does not exist: {canonical_repo}")
    if not canonical_repo.is_dir():
        raise ValueError("canonical_repo must be a directory")
    return canonical_repo.resolve()


def _paths_overlap(first: Path, second: Path) -> bool:
    """Return whether either resolved path contains the other."""
    return (
        first == second
        or first in second.parents
        or second in first.parents
    )


def _protected_manifest(workspace: Path) -> str:
    records: list[str] = []
    for name in ("task.md", CONTRACT_FILENAME):
        path = workspace / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"{name} must remain a non-symlink regular file")
        records.append(f"F\t{name}\t{hashlib.sha256(path.read_bytes()).hexdigest()}")
    evidence = workspace / "evidence"
    if evidence.is_symlink() or not evidence.is_dir():
        raise ValueError("evidence/ must remain a non-symlink directory")
    _reject_symlinks(evidence)
    records.append("D\tevidence")
    for current, directories, files in os.walk(evidence, followlinks=False):
        base = Path(current)
        for name in directories:
            records.append(f"D\t{(base / name).relative_to(workspace).as_posix()}")
        for name in files:
            path = base / name
            relative = path.relative_to(workspace).as_posix()
            records.append(
                f"F\t{relative}\t{hashlib.sha256(path.read_bytes()).hexdigest()}"
            )
    return hashlib.sha256(("\n".join(sorted(records)) + "\n").encode()).hexdigest()


def _root_layout_error(workspace: Path) -> str | None:
    entries = {path.name for path in workspace.iterdir()}
    if entries == _ROOT_ENTRIES:
        return None
    return f"Post-run workspace contains disallowed root entries: {sorted(entries)}"


def run_authorized_patch(
    workspace: Path,
    canonical_repo: Path,
    contract: ClinicalChangeContract,
    artifacts_dir: Path,
    *,
    model: str = "gpt-5.6-sol",
    timeout_seconds: float = 180.0,
) -> AuthorizedPatchRun:
    """Execute exactly one already-authorized patching call."""
    if not isinstance(contract, ClinicalChangeContract):
        raise ValueError("contract must be a ClinicalChangeContract")
    resolved_workspace = _validate_workspace(workspace)
    resolved_canonical = _validate_canonical_repo(canonical_repo)
    if _paths_overlap(resolved_workspace, resolved_canonical):
        raise ValueError(
            "canonical_repo must be outside and disjoint from the solver workspace"
        )
    if not isinstance(artifacts_dir, Path):
        raise ValueError("artifacts_dir must be a pathlib.Path")
    resolved_artifacts = artifacts_dir.resolve()
    if _paths_overlap(resolved_artifacts, resolved_canonical):
        raise ValueError(
            "artifacts_dir must be outside and disjoint from canonical_repo"
        )
    loaded_contract = load_contract(resolved_workspace / CONTRACT_FILENAME)
    if loaded_contract != contract:
        raise ValueError("workspace contract does not equal the supplied contract")
    if decide_change_action(contract) is not ChangeAction.PATCH:
        raise ValueError("authorized patch runner requires a PATCH contract")

    contract_sha256 = hashlib.sha256(contract_to_json(contract).encode("utf-8")).hexdigest()
    manifest_before = _protected_manifest(resolved_workspace)
    if not compare_repositories(resolved_canonical, resolved_workspace / "repo").is_clean:
        raise ValueError("workspace repo must initially match canonical_repo")

    codex_run = run_codex(
        resolved_workspace,
        artifacts_dir,
        AUTHORIZED_PATCH_PROMPT,
        model=model,
        timeout_seconds=timeout_seconds,
    )

    manifest_after: str | None
    failures: list[str] = []
    try:
        manifest_after = _protected_manifest(resolved_workspace)
    except (OSError, ValueError) as error:
        manifest_after = None
        failures.append(f"Protected inputs could not be safely verified: {error}")
    unchanged = manifest_after == manifest_before if manifest_after else False
    if manifest_after is not None and not unchanged:
        failures.append("Protected task, evidence, or contract inputs were modified")
    try:
        layout_error = _root_layout_error(resolved_workspace)
    except OSError as error:
        layout_error = f"Post-run workspace layout could not be inspected: {error}"
    if layout_error:
        failures.append(layout_error)
    if codex_run.timed_out:
        failures.append("Codex patch process timed out")
    elif codex_run.returncode != 0:
        failures.append(f"Codex patch process exited with return code {codex_run.returncode}")

    if failures or not codex_run.completed_successfully:
        return AuthorizedPatchRun(
            codex_run, None, AUTHORIZED_PATCH_PROMPT_SHA256, contract_sha256,
            manifest_before, manifest_after, unchanged,
            _bounded_error("; ".join(failures)),
        )

    try:
        repository_diff = compare_repositories(
            resolved_canonical, resolved_workspace / "repo"
        )
    except (FileNotFoundError, OSError, ValueError) as error:
        return AuthorizedPatchRun(
            codex_run, None, AUTHORIZED_PATCH_PROMPT_SHA256, contract_sha256,
            manifest_before, manifest_after, unchanged,
            _bounded_error(f"Repository output could not be safely compared: {error}"),
        )
    return AuthorizedPatchRun(
        codex_run, repository_diff, AUTHORIZED_PATCH_PROMPT_SHA256,
        contract_sha256, manifest_before, manifest_after, True, None,
    )
