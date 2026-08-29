"""Reproducible experiment harness for the frozen EvidencePatch workflow."""

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile

from evidencepatch.benchmark_evaluation import (
    BenchmarkEvaluation,
    aggregate_case_evaluations,
)
from evidencepatch.case_evaluator import evaluate_case
from evidencepatch.case_validation import validate_case
from evidencepatch.change_contract import ChangeAction
from evidencepatch.codex_runner import CodexRunResult
from evidencepatch.contract_runner import CONTRACT_EXTRACTION_PROMPT_SHA256
from evidencepatch.evaluation_types import CaseEvaluation
from evidencepatch.patch_runner import AUTHORIZED_PATCH_PROMPT_SHA256
from evidencepatch.result_contract import SolverResult
from evidencepatch.workflow import EvidencePatchWorkflowRun, run_evidencepatch_workflow
from evidencepatch.workspace import prepare_case_workspace


_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class AdvancedCaseRun:
    """Persisted observed workflow and evaluation outcome for one case."""

    case_id: str
    action: ChangeAction | None
    workflow_completed_successfully: bool
    workflow_error: str | None
    codex_call_count: int
    total_codex_duration_seconds: float
    extraction_codex_run: CodexRunResult
    patch_codex_run: CodexRunResult | None
    solver_result: SolverResult | None
    evaluation: CaseEvaluation
    workspace_snapshot: Path
    evaluation_path: Path
    workflow_metadata_path: Path

    def __post_init__(self) -> None:
        if (
            not isinstance(self.case_id, str)
            or not self.case_id
            or self.case_id != self.case_id.strip()
        ):
            raise ValueError("case_id must be a non-empty stripped string")
        if self.action is not None and not isinstance(self.action, ChangeAction):
            raise ValueError("action must be a ChangeAction or None")
        if not isinstance(self.workflow_completed_successfully, bool):
            raise ValueError("workflow_completed_successfully must be a boolean")
        if self.workflow_error is not None and (
            not isinstance(self.workflow_error, str)
            or not self.workflow_error
            or self.workflow_error != self.workflow_error.strip()
        ):
            raise ValueError("workflow_error must be None or a non-empty stripped string")
        if (
            isinstance(self.codex_call_count, bool)
            or not isinstance(self.codex_call_count, int)
            or self.codex_call_count not in {1, 2}
        ):
            raise ValueError("codex_call_count must be integer 1 or 2")
        if (
            isinstance(self.total_codex_duration_seconds, bool)
            or not isinstance(self.total_codex_duration_seconds, (int, float))
            or not math.isfinite(self.total_codex_duration_seconds)
            or self.total_codex_duration_seconds < 0
        ):
            raise ValueError("total_codex_duration_seconds must be finite and non-negative")
        if not isinstance(self.extraction_codex_run, CodexRunResult):
            raise ValueError("extraction_codex_run must be a CodexRunResult")
        if self.patch_codex_run is not None and not isinstance(
            self.patch_codex_run, CodexRunResult
        ):
            raise ValueError("patch_codex_run must be a CodexRunResult or None")
        if (self.codex_call_count == 1) != (self.patch_codex_run is None):
            raise ValueError("codex_call_count must agree with patch_codex_run presence")
        if self.solver_result is not None and not isinstance(
            self.solver_result, SolverResult
        ):
            raise ValueError("solver_result must be a SolverResult or None")
        if not isinstance(self.evaluation, CaseEvaluation):
            raise ValueError("evaluation must be a CaseEvaluation")
        if self.evaluation.case_id != self.case_id:
            raise ValueError("evaluation case_id must match case_id")
        for name in ("workspace_snapshot", "evaluation_path", "workflow_metadata_path"):
            if not isinstance(getattr(self, name), Path):
                raise ValueError(f"{name} must be a pathlib.Path")
        if self.workflow_completed_successfully:
            if self.action is None or self.solver_result is None or self.workflow_error is not None:
                raise ValueError("successful workflow requires action, solver result, and no error")
            if self.solver_result.action != self.action.value:
                raise ValueError("solver_result action must match action")
        elif self.solver_result is not None or self.workflow_error is None:
            raise ValueError("failed workflow requires no solver result and a workflow error")

    @property
    def verified_success(self) -> bool:
        """Return the frozen complete case-evaluation outcome."""
        return self.evaluation.passed


@dataclass(frozen=True)
class AdvancedBenchmarkRun:
    """Persisted aggregate outcome of an advanced EvidencePatch experiment."""

    model: str
    contract_prompt_sha256: str
    patch_prompt_sha256: str
    cases: tuple[AdvancedCaseRun, ...]
    evaluation: BenchmarkEvaluation
    output_dir: Path
    metadata_path: Path
    summary_path: Path

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model or self.model != self.model.strip():
            raise ValueError("model must be a non-empty stripped string")
        for value, name in (
            (self.contract_prompt_sha256, "contract_prompt_sha256"),
            (self.patch_prompt_sha256, "patch_prompt_sha256"),
        ):
            if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
                raise ValueError(f"{name} must be 64 lowercase hexadecimal characters")
        if not isinstance(self.cases, tuple) or not self.cases:
            raise ValueError("cases must be a non-empty tuple")
        if any(not isinstance(case, AdvancedCaseRun) for case in self.cases):
            raise ValueError("cases must contain AdvancedCaseRun values")
        ids = [case.case_id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("case IDs must be unique")
        if not isinstance(self.evaluation, BenchmarkEvaluation):
            raise ValueError("evaluation must be a BenchmarkEvaluation")
        if self.evaluation.cases != tuple(case.evaluation for case in self.cases):
            raise ValueError("evaluation cases must match case-run evaluations")
        for name in ("output_dir", "metadata_path", "summary_path"):
            if not isinstance(getattr(self, name), Path):
                raise ValueError(f"{name} must be a pathlib.Path")

    @property
    def total_codex_calls(self) -> int:
        return sum(case.codex_call_count for case in self.cases)

    @property
    def total_codex_duration_seconds(self) -> float:
        return sum(case.total_codex_duration_seconds for case in self.cases)

    @property
    def workflow_failure_cases(self) -> tuple[str, ...]:
        return tuple(
            case.case_id for case in self.cases
            if not case.workflow_completed_successfully
        )

    @property
    def timed_out_invocations(self) -> tuple[str, ...]:
        return tuple(self._stage_labels("timed_out"))

    @property
    def nonzero_exit_invocations(self) -> tuple[str, ...]:
        labels: list[str] = []
        for case in self.cases:
            for stage, run in (("extraction", case.extraction_codex_run), ("patch", case.patch_codex_run)):
                if run is not None and not run.timed_out and run.returncode not in (None, 0):
                    labels.append(f"{case.case_id}:{stage}")
        return tuple(labels)

    def _stage_labels(self, attribute: str) -> list[str]:
        labels: list[str] = []
        for case in self.cases:
            for stage, run in (("extraction", case.extraction_codex_run), ("patch", case.patch_codex_run)):
                if run is not None and getattr(run, attribute):
                    labels.append(f"{case.case_id}:{stage}")
        return labels


def _positive_timeout(value: object, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{name} must be a positive finite number")
    return value


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def _prepare_output_dir(output_dir: Path, case_dirs: tuple[Path, ...]) -> Path:
    if not isinstance(output_dir, Path):
        raise ValueError("output_dir must be a pathlib.Path")
    if output_dir.is_symlink():
        raise ValueError("output_dir must not be a symlink")
    resolved = output_dir.resolve()
    for case_dir in case_dirs:
        if _paths_overlap(resolved, case_dir.resolve()):
            raise ValueError("output_dir must be outside and disjoint from every case")
    if output_dir.exists():
        if not output_dir.is_dir():
            raise ValueError("output_dir must be a directory")
        if any(output_dir.iterdir()):
            raise ValueError("output_dir must be empty")
    else:
        output_dir.mkdir(parents=True)
    return output_dir.resolve()


def _reject_symlinks(root: Path) -> None:
    for current, directories, files in os.walk(root, followlinks=False):
        base = Path(current)
        for name in (*directories, *files):
            if (base / name).is_symlink():
                raise RuntimeError(f"public solver workspace contains a symlink: {base / name}")


def _assert_public_workspace(workspace: Path) -> None:
    _reject_symlinks(workspace)
    entries = {path.name for path in workspace.iterdir()}
    if entries != {"task.md", "evidence", "repo"}:
        raise RuntimeError(f"prepared workspace has unexpected root entries: {sorted(entries)}")
    if not (workspace / "task.md").is_file():
        raise RuntimeError("prepared workspace is missing task.md")
    if not (workspace / "evidence").is_dir() or not (workspace / "repo").is_dir():
        raise RuntimeError("prepared workspace is missing evidence/ or repo/")
    if (workspace / "hidden").exists() or list(workspace.rglob("ground_truth.json")):
        raise RuntimeError("prepared workspace contains private benchmark material")
    for name in ("evidencepatch_contract.json", "evidencepatch_result.json"):
        if (workspace / name).exists() or (workspace / name).is_symlink():
            raise RuntimeError(f"prepared workspace unexpectedly contains {name}")


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _evaluation_data(evaluation: CaseEvaluation) -> dict[str, object]:
    return {
        "schema_version": 1,
        "case_id": evaluation.case_id,
        "verified_success": evaluation.passed,
        "checks": [
            {"name": check.name, "passed": check.passed, "detail": check.detail}
            for check in evaluation.checks
        ],
    }


def _solver_mapping(result: SolverResult | None) -> dict[str, object] | None:
    if result is None:
        return None
    return {
        "schema_version": result.schema_version,
        "action": result.action,
        "changed_files": list(result.changed_files),
        "evidence_ids": list(result.evidence_ids),
        "human_review_required": result.human_review_required,
        "summary": result.summary,
    }


def _workflow_data(case_id: str, run: EvidencePatchWorkflowRun) -> dict[str, object]:
    extraction = run.extraction_run.codex_run
    patch = run.patch_run.codex_run if run.patch_run is not None else None
    return {
        "schema_version": 1,
        "case_id": case_id,
        "workflow_completed_successfully": run.completed_successfully,
        "action": run.action.value if run.action is not None else None,
        "workflow_error": run.error,
        "codex_call_count": run.codex_call_count,
        "total_codex_duration_seconds": run.total_codex_duration_seconds,
        "extraction": {
            "prompt_sha256": CONTRACT_EXTRACTION_PROMPT_SHA256,
            "model": extraction.model,
            "codex_version": extraction.codex_version,
            "returncode": extraction.returncode,
            "timed_out": extraction.timed_out,
            "duration_seconds": extraction.duration_seconds,
        },
        "patch": None if patch is None else {
            "prompt_sha256": AUTHORIZED_PATCH_PROMPT_SHA256,
            "model": patch.model,
            "codex_version": patch.codex_version,
            "returncode": patch.returncode,
            "timed_out": patch.timed_out,
            "duration_seconds": patch.duration_seconds,
        },
        "solver_result": _solver_mapping(run.solver_result),
    }


def _summary_data(run: AdvancedBenchmarkRun) -> dict[str, object]:
    action_counts = {name: 0 for name in ("PATCH", "NO_PATCH", "ESCALATE", "UNRESOLVED")}
    for case in run.cases:
        action_counts[case.action.value if case.action is not None else "UNRESOLVED"] += 1
    return {
        "schema_version": 1,
        "experiment": "evidencepatch_advanced",
        "model": run.model,
        "contract_extraction_prompt_sha256": run.contract_prompt_sha256,
        "authorized_patch_prompt_sha256": run.patch_prompt_sha256,
        "total_cases": run.evaluation.total_cases,
        "verified_successes": run.evaluation.verified_successes,
        "verified_failures": run.evaluation.verified_failures,
        "vusr": run.evaluation.vusr,
        "total_codex_calls": run.total_codex_calls,
        "total_codex_duration_seconds": run.total_codex_duration_seconds,
        "workflow_failure_cases": list(run.workflow_failure_cases),
        "timed_out_invocations": list(run.timed_out_invocations),
        "nonzero_exit_invocations": list(run.nonzero_exit_invocations),
        "action_counts": action_counts,
        "check_metrics": [
            {"name": metric.name, "passed_cases": metric.passed_cases,
             "total_cases": metric.total_cases, "rate": metric.rate}
            for metric in run.evaluation.check_metrics
        ],
        "cases": [
            {
                "case_id": case.case_id,
                "workflow_completed_successfully": case.workflow_completed_successfully,
                "action": case.action.value if case.action is not None else None,
                "verified_success": case.verified_success,
                "failed_checks": [check.name for check in case.evaluation.failed_checks],
                "codex_call_count": case.codex_call_count,
                "total_codex_duration_seconds": case.total_codex_duration_seconds,
                "extraction_returncode": case.extraction_codex_run.returncode,
                "extraction_timed_out": case.extraction_codex_run.timed_out,
                "patch_returncode": case.patch_codex_run.returncode if case.patch_codex_run else None,
                "patch_timed_out": case.patch_codex_run.timed_out if case.patch_codex_run else None,
            }
            for case in run.cases
        ],
    }


def run_advanced_benchmark(
    case_dirs: tuple[Path, ...],
    output_dir: Path,
    *,
    model: str = "gpt-5.6-sol",
    extraction_timeout_seconds: float = 180.0,
    patch_timeout_seconds: float = 180.0,
    hidden_timeout_seconds: float = 30.0,
) -> AdvancedBenchmarkRun:
    """Run the frozen advanced workflow once per case and persist observations."""
    if not isinstance(case_dirs, tuple) or not case_dirs:
        raise ValueError("case_dirs must be a non-empty tuple")
    if any(not isinstance(case, Path) for case in case_dirs):
        raise ValueError("case_dirs must contain pathlib.Path values")
    if not isinstance(model, str) or not model or model != model.strip():
        raise ValueError("model must be a non-empty stripped string")
    _positive_timeout(extraction_timeout_seconds, "extraction_timeout_seconds")
    _positive_timeout(patch_timeout_seconds, "patch_timeout_seconds")
    _positive_timeout(hidden_timeout_seconds, "hidden_timeout_seconds")
    for case in case_dirs:
        validate_case(case)
    case_ids = [case.name for case in case_dirs]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("case directory names must be unique")
    resolved_output = _prepare_output_dir(output_dir, case_dirs)

    metadata_path = resolved_output / "experiment_metadata.json"
    _write_json(metadata_path, {
        "schema_version": 1,
        "experiment": "evidencepatch_advanced",
        "model": model,
        "contract_extraction_prompt_sha256": CONTRACT_EXTRACTION_PROMPT_SHA256,
        "authorized_patch_prompt_sha256": AUTHORIZED_PATCH_PROMPT_SHA256,
        "case_ids": case_ids,
        "extraction_timeout_seconds": extraction_timeout_seconds,
        "patch_timeout_seconds": patch_timeout_seconds,
        "hidden_timeout_seconds": hidden_timeout_seconds,
        "retry_policy": "none",
        "web_search_enabled": False,
        "human_feedback_during_run": False,
        "extraction_invocations_per_case": 1,
        "patch_invocation_policy": "exactly_one_if_governance_action_is_PATCH",
        "governance": "frozen_deterministic_change_action_gate",
        "result_generation": "deterministic_without_model_call",
    })

    case_runs: list[AdvancedCaseRun] = []
    for case_dir, case_id in zip(case_dirs, case_ids, strict=True):
        case_output = resolved_output / case_id
        case_output.mkdir()
        with tempfile.TemporaryDirectory(prefix=f"evidencepatch-advanced-{case_id}-") as temporary:
            temporary_root = Path(temporary)
            workspace = prepare_case_workspace(case_dir, temporary_root / "workspace")
            _assert_public_workspace(workspace)
            canonical_repo = temporary_root / "canonical_repo"
            shutil.copytree(workspace / "repo", canonical_repo)
            workflow_run = run_evidencepatch_workflow(
                workspace,
                canonical_repo,
                case_output / "extraction_codex",
                case_output / "patch_codex",
                model=model,
                extraction_timeout_seconds=extraction_timeout_seconds,
                patch_timeout_seconds=patch_timeout_seconds,
            )
            evaluation = evaluate_case(
                case_dir, workspace, hidden_timeout_seconds=hidden_timeout_seconds
            )
            _reject_symlinks(workspace)
            workspace_snapshot = case_output / "workspace"
            shutil.copytree(workspace, workspace_snapshot)

            extraction_run = workflow_run.extraction_run.codex_run
            patch_run = (
                workflow_run.patch_run.codex_run
                if workflow_run.patch_run is not None else None
            )
            solver_result = workflow_run.solver_result
            action = workflow_run.action
            workflow_success = workflow_run.completed_successfully
            workflow_error = workflow_run.error
            call_count = workflow_run.codex_call_count
            duration = workflow_run.total_codex_duration_seconds

        evaluation_path = case_output / "evaluation.json"
        workflow_path = case_output / "workflow.json"
        _write_json(evaluation_path, _evaluation_data(evaluation))
        _write_json(workflow_path, _workflow_data(case_id, workflow_run))
        case_runs.append(AdvancedCaseRun(
            case_id, action, workflow_success, workflow_error, call_count, duration,
            extraction_run, patch_run, solver_result, evaluation,
            workspace_snapshot, evaluation_path, workflow_path,
        ))

    aggregate = aggregate_case_evaluations(tuple(case.evaluation for case in case_runs))
    summary_path = resolved_output / "benchmark_summary.json"
    run = AdvancedBenchmarkRun(
        model, CONTRACT_EXTRACTION_PROMPT_SHA256, AUTHORIZED_PATCH_PROMPT_SHA256,
        tuple(case_runs), aggregate, resolved_output, metadata_path, summary_path,
    )
    _write_json(summary_path, _summary_data(run))
    return run
