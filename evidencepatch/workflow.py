"""Deterministic orchestration of the frozen EvidencePatch stages."""

from dataclasses import dataclass
import json
from pathlib import Path

from evidencepatch.change_contract import (
    ChangeAction,
    decide_change_action,
    requires_human_review,
)
from evidencepatch.contract_runner import (
    ContractExtractionRun,
    run_contract_extraction,
)
from evidencepatch.patch_runner import AuthorizedPatchRun, run_authorized_patch
from evidencepatch.repo_diff import RepositoryDiff, compare_repositories
from evidencepatch.result_contract import (
    RESULT_FILENAME,
    SolverResult,
    load_solver_result,
    validate_solver_result,
)


_FINAL_ROOT_ENTRIES = {
    "task.md",
    "evidence",
    "repo",
    "evidencepatch_contract.json",
    RESULT_FILENAME,
}
_ERROR_LIMIT = 500


@dataclass(frozen=True)
class EvidencePatchWorkflowRun:
    """Complete outcome of one deterministic EvidencePatch workflow."""

    extraction_run: ContractExtractionRun
    action: ChangeAction | None
    patch_run: AuthorizedPatchRun | None
    solver_result: SolverResult | None
    result_path: Path
    error: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.extraction_run, ContractExtractionRun):
            raise ValueError("extraction_run must be a ContractExtractionRun")
        if self.action is not None and not isinstance(self.action, ChangeAction):
            raise ValueError("action must be a ChangeAction or None")
        if self.patch_run is not None and not isinstance(
            self.patch_run, AuthorizedPatchRun
        ):
            raise ValueError("patch_run must be an AuthorizedPatchRun or None")
        if self.solver_result is not None and not isinstance(
            self.solver_result, SolverResult
        ):
            raise ValueError("solver_result must be a SolverResult or None")
        if not isinstance(self.result_path, Path):
            raise ValueError("result_path must be a pathlib.Path")
        if self.error is not None and (
            not isinstance(self.error, str)
            or not self.error
            or self.error != self.error.strip()
        ):
            raise ValueError("error must be None or a non-empty stripped string")

        success = (
            self.extraction_run.completed_successfully
            and self.action is not None
            and self.solver_result is not None
            and self.error is None
        )
        if success:
            if self.solver_result.action != self.action.value:
                raise ValueError("solver_result action must match workflow action")
            if self.action is ChangeAction.PATCH:
                if (
                    self.patch_run is None
                    or not self.patch_run.completed_successfully
                    or self.patch_run.repository_diff is None
                    or self.patch_run.repository_diff.is_clean
                ):
                    raise ValueError(
                        "successful PATCH requires a successful non-clean patch run"
                    )
            elif self.patch_run is not None:
                raise ValueError("successful non-PATCH workflow must not have a patch run")
        elif self.solver_result is not None or self.error is None:
            raise ValueError(
                "failed workflow must have solver_result=None and a non-empty error"
            )

    @property
    def completed_successfully(self) -> bool:
        """Return whether every required stage and final result succeeded."""
        return (
            self.extraction_run.completed_successfully
            and self.action is not None
            and self.solver_result is not None
            and self.error is None
        )

    @property
    def codex_call_count(self) -> int:
        """Return the number of represented extraction and patch invocations."""
        return 1 if self.patch_run is None else 2

    @property
    def total_codex_duration_seconds(self) -> float:
        """Return total elapsed Codex duration across represented stages."""
        duration = self.extraction_run.codex_run.duration_seconds
        if self.patch_run is not None:
            duration += self.patch_run.codex_run.duration_seconds
        return duration


def _bounded_error(error: object) -> str:
    text = " ".join(str(error).split()) or "Unknown workflow failure"
    return text if len(text) <= _ERROR_LIMIT else text[: _ERROR_LIMIT - 3] + "..."


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def _validate_directory(path: object, name: str) -> Path:
    if not isinstance(path, Path):
        raise ValueError(f"{name} must be a pathlib.Path")
    if path.is_symlink():
        raise ValueError(f"{name} must not be a symlink")
    if not path.exists():
        raise FileNotFoundError(f"{name} does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"{name} must be a directory")
    return path.resolve()


def _failure(
    extraction_run: ContractExtractionRun,
    result_path: Path,
    error: object,
    *,
    action: ChangeAction | None = None,
    patch_run: AuthorizedPatchRun | None = None,
) -> EvidencePatchWorkflowRun:
    return EvidencePatchWorkflowRun(
        extraction_run=extraction_run,
        action=action,
        patch_run=patch_run,
        solver_result=None,
        result_path=result_path,
        error=_bounded_error(error),
    )


def _remove_created_result(result_path: Path, created: bool) -> None:
    if created and result_path.exists() and not result_path.is_symlink() and result_path.is_file():
        try:
            result_path.unlink()
        except OSError:
            pass


def run_evidencepatch_workflow(
    workspace: Path,
    canonical_repo: Path,
    extraction_artifacts_dir: Path,
    patch_artifacts_dir: Path,
    *,
    model: str = "gpt-5.6-sol",
    extraction_timeout_seconds: float = 180.0,
    patch_timeout_seconds: float = 180.0,
) -> EvidencePatchWorkflowRun:
    """Run extraction, deterministic governance, and any authorized patch once."""
    resolved_workspace = _validate_directory(workspace, "workspace")
    resolved_canonical = _validate_directory(canonical_repo, "canonical_repo")
    if not isinstance(extraction_artifacts_dir, Path):
        raise ValueError("extraction_artifacts_dir must be a pathlib.Path")
    if not isinstance(patch_artifacts_dir, Path):
        raise ValueError("patch_artifacts_dir must be a pathlib.Path")
    if _paths_overlap(resolved_workspace, resolved_canonical):
        raise ValueError(
            "canonical_repo must be outside and disjoint from the solver workspace"
        )
    if not compare_repositories(
        resolved_canonical, resolved_workspace / "repo"
    ).is_clean:
        raise ValueError("workspace repo must initially match canonical_repo")

    result_path = resolved_workspace / RESULT_FILENAME
    if result_path.exists() or result_path.is_symlink():
        raise ValueError(f"result path must not already exist: {result_path}")

    extraction_run = run_contract_extraction(
        resolved_workspace,
        extraction_artifacts_dir,
        model=model,
        timeout_seconds=extraction_timeout_seconds,
    )
    if not extraction_run.completed_successfully:
        return _failure(
            extraction_run,
            result_path,
            f"Contract extraction failed: {extraction_run.error}",
        )

    contract = extraction_run.contract
    if contract is None:
        return _failure(extraction_run, result_path, "Successful extraction had no contract")
    action = decide_change_action(contract)
    patch_run: AuthorizedPatchRun | None = None

    if action is ChangeAction.PATCH:
        patch_run = run_authorized_patch(
            resolved_workspace,
            resolved_canonical,
            contract,
            patch_artifacts_dir,
            model=model,
            timeout_seconds=patch_timeout_seconds,
        )
        if not patch_run.completed_successfully:
            return _failure(
                extraction_run,
                result_path,
                f"Authorized patch failed: {patch_run.error}",
                action=action,
                patch_run=patch_run,
            )
        repository_diff = patch_run.repository_diff
        if repository_diff is None or repository_diff.is_clean:
            return _failure(
                extraction_run,
                result_path,
                "Authorized PATCH produced no repository changes",
                action=action,
                patch_run=patch_run,
            )
        changed_files = list(repository_diff.changed_files)
    else:
        try:
            repository_diff = compare_repositories(
                resolved_canonical, resolved_workspace / "repo"
            )
        except (FileNotFoundError, OSError, ValueError) as error:
            return _failure(
                extraction_run, result_path,
                f"Final repository safety comparison failed: {error}", action=action,
            )
        if not repository_diff.is_clean:
            return _failure(
                extraction_run, result_path,
                f"{action.value} requires an unchanged repository", action=action,
            )
        changed_files = []

    mapping = {
        "schema_version": 1,
        "action": action.value,
        "changed_files": changed_files,
        "evidence_ids": [item.evidence_id for item in contract.evidence],
        "human_review_required": requires_human_review(action),
        "summary": f"{action.value}: {contract.rationale}",
    }
    try:
        validated_result = validate_solver_result(mapping)
    except (TypeError, ValueError) as error:
        return _failure(
            extraction_run, result_path, f"Final result validation failed: {error}",
            action=action, patch_run=patch_run,
        )

    created = False
    try:
        if result_path.exists() or result_path.is_symlink():
            raise ValueError("result path appeared before final write")
        created = True
        result_path.write_text(
            json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        loaded_result = load_solver_result(result_path)
        if loaded_result != validated_result:
            raise ValueError("written result did not round-trip exactly")
        entries = {path.name for path in resolved_workspace.iterdir()}
        if entries != _FINAL_ROOT_ENTRIES:
            raise ValueError(f"final workspace root contains unexpected entries: {sorted(entries)}")
    except (FileNotFoundError, OSError, ValueError) as error:
        _remove_created_result(result_path, created)
        return _failure(
            extraction_run, result_path, f"Final result persistence failed: {error}",
            action=action, patch_run=patch_run,
        )

    return EvidencePatchWorkflowRun(
        extraction_run, action, patch_run, loaded_result, result_path, None
    )
