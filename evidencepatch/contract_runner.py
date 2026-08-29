"""Isolated one-call runner for Clinical Change Contract extraction."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re

from evidencepatch.change_contract import ClinicalChangeContract
from evidencepatch.codex_runner import CodexRunResult, run_codex
from evidencepatch.contract_extraction import (
    CONTRACT_EXTRACTION_PROMPT,
    CONTRACT_FILENAME,
    load_contract,
)


CONTRACT_EXTRACTION_PROMPT_SHA256 = hashlib.sha256(
    CONTRACT_EXTRACTION_PROMPT.encode("utf-8")
).hexdigest()

_INITIAL_ROOT_ENTRIES = {"task.md", "evidence", "repo"}
_FINAL_ROOT_ENTRIES = _INITIAL_ROOT_ENTRIES | {CONTRACT_FILENAME}
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_ERROR_LIMIT = 500


@dataclass(frozen=True)
class ContractExtractionRun:
    """Outcome of one isolated contract-extraction invocation."""

    codex_run: CodexRunResult
    contract: ClinicalChangeContract | None
    contract_path: Path
    prompt_sha256: str
    public_input_manifest_before: str
    public_input_manifest_after: str | None
    public_inputs_unchanged: bool
    error: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.codex_run, CodexRunResult):
            raise ValueError("codex_run must be a CodexRunResult")
        if self.contract is not None and not isinstance(
            self.contract, ClinicalChangeContract
        ):
            raise ValueError("contract must be a ClinicalChangeContract or None")
        if not isinstance(self.contract_path, Path):
            raise ValueError("contract_path must be a Path")
        _validate_digest(self.prompt_sha256, "prompt_sha256")
        _validate_digest(
            self.public_input_manifest_before, "public_input_manifest_before"
        )
        if self.public_input_manifest_after is not None:
            _validate_digest(
                self.public_input_manifest_after, "public_input_manifest_after"
            )
        if not isinstance(self.public_inputs_unchanged, bool):
            raise ValueError("public_inputs_unchanged must be a boolean")
        if self.error is not None and (
            not isinstance(self.error, str)
            or not self.error
            or self.error != self.error.strip()
        ):
            raise ValueError("error must be None or a non-empty stripped string")

        successful = (
            self.codex_run.completed_successfully
            and self.contract is not None
            and self.error is None
            and self.public_inputs_unchanged
            and self.public_input_manifest_after is not None
        )
        if not successful and (self.contract is not None or self.error is None):
            raise ValueError(
                "failed extraction must have contract=None and a non-empty error"
            )

    @property
    def completed_successfully(self) -> bool:
        """Return whether process, integrity, and strict parsing all succeeded."""
        return (
            self.codex_run.completed_successfully
            and self.contract is not None
            and self.error is None
            and self.public_inputs_unchanged
            and self.public_input_manifest_after is not None
        )


def _validate_digest(value: object, name: str) -> None:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be exactly 64 lowercase hexadecimal characters")


def _bounded_error(error: object) -> str:
    text = " ".join(str(error).split()) or "Unknown extraction failure"
    if len(text) <= _ERROR_LIMIT:
        return text
    return text[: _ERROR_LIMIT - 3] + "..."


def _reject_symlinks(root: Path) -> None:
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in (*directories, *files):
            path = current_path / name
            if path.is_symlink():
                raise ValueError(f"Public inputs must not contain symlinks: {path}")


def _validate_initial_workspace(workspace: Path) -> Path:
    if not isinstance(workspace, Path):
        raise ValueError("workspace must be a pathlib.Path")
    if workspace.is_symlink():
        raise ValueError("workspace must not be a symlink")
    if not workspace.exists():
        raise FileNotFoundError(f"workspace does not exist: {workspace}")
    if not workspace.is_dir():
        raise ValueError(f"workspace is not a directory: {workspace}")

    entries = {path.name for path in workspace.iterdir()}
    if entries != _INITIAL_ROOT_ENTRIES:
        raise ValueError(
            "workspace must initially contain exactly task.md, evidence, and repo; "
            f"found {sorted(entries)}"
        )

    task = workspace / "task.md"
    evidence = workspace / "evidence"
    repo = workspace / "repo"
    if task.is_symlink() or not task.is_file():
        raise ValueError("task.md must be a non-symlink regular file")
    for path, name in ((evidence, "evidence"), (repo, "repo")):
        if path.is_symlink() or not path.is_dir():
            raise ValueError(f"{name}/ must be a non-symlink directory")
        _reject_symlinks(path)
        if not any(candidate.is_file() for candidate in path.rglob("*")):
            raise ValueError(f"{name}/ must contain at least one regular file")
    return workspace.resolve()


def _public_input_manifest(workspace: Path) -> str:
    task = workspace / "task.md"
    if task.is_symlink() or not task.is_file():
        raise ValueError("task.md must remain a non-symlink regular file")

    records: list[str] = []
    records.append(f"F\ttask.md\t{hashlib.sha256(task.read_bytes()).hexdigest()}")
    for root_name in ("evidence", "repo"):
        root = workspace / root_name
        if root.is_symlink() or not root.is_dir():
            raise ValueError(f"{root_name}/ must remain a non-symlink directory")
        _reject_symlinks(root)
        records.append(f"D\t{root_name}")
        for current, directories, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            for name in directories:
                path = current_path / name
                relative = path.relative_to(workspace).as_posix()
                records.append(f"D\t{relative}")
            for name in files:
                path = current_path / name
                relative = path.relative_to(workspace).as_posix()
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                records.append(f"F\t{relative}\t{digest}")
    payload = "\n".join(sorted(records)) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _root_layout_error(workspace: Path) -> str | None:
    entries = {path.name for path in workspace.iterdir()}
    if entries == _FINAL_ROOT_ENTRIES:
        return None
    return (
        "Post-run workspace must contain only task.md, evidence, repo, and "
        f"{CONTRACT_FILENAME}; found {sorted(entries)}"
    )


def run_contract_extraction(
    workspace: Path,
    artifacts_dir: Path,
    *,
    model: str = "gpt-5.6-sol",
    timeout_seconds: float = 180.0,
) -> ContractExtractionRun:
    """Run one extraction call and strictly validate its isolated artifact."""
    resolved_workspace = _validate_initial_workspace(workspace)
    manifest_before = _public_input_manifest(resolved_workspace)
    codex_run = run_codex(
        resolved_workspace,
        artifacts_dir,
        CONTRACT_EXTRACTION_PROMPT,
        model=model,
        timeout_seconds=timeout_seconds,
    )
    contract_path = resolved_workspace / CONTRACT_FILENAME

    manifest_after: str | None
    manifest_error: str | None = None
    try:
        manifest_after = _public_input_manifest(resolved_workspace)
    except (OSError, ValueError) as error:
        manifest_after = None
        manifest_error = f"Public inputs could not be safely verified: {error}"
    inputs_unchanged = manifest_after == manifest_before if manifest_after else False

    failures: list[str] = []
    if manifest_error:
        failures.append(manifest_error)
    elif not inputs_unchanged:
        failures.append("Public task, evidence, or repository inputs were modified")

    try:
        layout_error = _root_layout_error(resolved_workspace)
    except OSError as error:
        layout_error = f"Post-run workspace layout could not be inspected: {error}"
    if layout_error:
        failures.append(layout_error)

    if codex_run.timed_out:
        failures.append("Codex extraction process timed out")
    elif codex_run.returncode != 0:
        failures.append(
            f"Codex extraction process exited with return code {codex_run.returncode}"
        )

    if failures or not codex_run.completed_successfully:
        return ContractExtractionRun(
            codex_run=codex_run,
            contract=None,
            contract_path=contract_path,
            prompt_sha256=CONTRACT_EXTRACTION_PROMPT_SHA256,
            public_input_manifest_before=manifest_before,
            public_input_manifest_after=manifest_after,
            public_inputs_unchanged=inputs_unchanged,
            error=_bounded_error("; ".join(failures)),
        )

    try:
        contract = load_contract(contract_path)
    except (FileNotFoundError, OSError, ValueError) as error:
        return ContractExtractionRun(
            codex_run=codex_run,
            contract=None,
            contract_path=contract_path,
            prompt_sha256=CONTRACT_EXTRACTION_PROMPT_SHA256,
            public_input_manifest_before=manifest_before,
            public_input_manifest_after=manifest_after,
            public_inputs_unchanged=inputs_unchanged,
            error=_bounded_error(f"Contract artifact was invalid: {error}"),
        )

    return ContractExtractionRun(
        codex_run=codex_run,
        contract=contract,
        contract_path=contract_path,
        prompt_sha256=CONTRACT_EXTRACTION_PROMPT_SHA256,
        public_input_manifest_before=manifest_before,
        public_input_manifest_after=manifest_after,
        public_inputs_unchanged=True,
        error=None,
    )
