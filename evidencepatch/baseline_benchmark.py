"""Reproducible multi-case orchestration for the plain Codex baseline."""

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile

from evidencepatch.baseline_prompt import BASELINE_PROMPT
from evidencepatch.benchmark_evaluation import (
    BenchmarkEvaluation,
    aggregate_case_evaluations,
)
from evidencepatch.case_evaluator import evaluate_case
from evidencepatch.case_validation import validate_case
from evidencepatch.codex_runner import CodexRunResult, run_codex
from evidencepatch.evaluation_types import CaseEvaluation
from evidencepatch.workspace import prepare_case_workspace


@dataclass(frozen=True)
class BaselineCaseRun:
    """Persisted solver and evaluation outcome for one baseline case."""

    case_id: str
    codex_run: CodexRunResult
    evaluation: CaseEvaluation
    workspace_snapshot: Path
    evaluation_path: Path

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id.strip():
            raise ValueError("BaselineCaseRun case_id must be a non-empty string")
        if not isinstance(self.codex_run, CodexRunResult):
            raise ValueError("BaselineCaseRun codex_run must be a CodexRunResult")
        if not isinstance(self.evaluation, CaseEvaluation):
            raise ValueError("BaselineCaseRun evaluation must be a CaseEvaluation")
        if self.evaluation.case_id != self.case_id:
            raise ValueError("BaselineCaseRun evaluation case_id must match case_id")
        if not isinstance(self.workspace_snapshot, Path):
            raise ValueError("BaselineCaseRun workspace_snapshot must be a Path")
        if not isinstance(self.evaluation_path, Path):
            raise ValueError("BaselineCaseRun evaluation_path must be a Path")

    @property
    def verified_success(self) -> bool:
        """Return the complete seven-check evaluation outcome."""
        return self.evaluation.passed


@dataclass(frozen=True)
class BaselineBenchmarkRun:
    """Persisted aggregate result for one plain-Codex experiment."""

    model: str
    prompt_sha256: str
    cases: tuple[BaselineCaseRun, ...]
    evaluation: BenchmarkEvaluation
    output_dir: Path
    summary_path: Path

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("BaselineBenchmarkRun model must be a non-empty string")
        if not isinstance(self.prompt_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.prompt_sha256
        ):
            raise ValueError(
                "BaselineBenchmarkRun prompt_sha256 must be 64 lowercase hexadecimal characters"
            )
        if not isinstance(self.cases, tuple) or not self.cases:
            raise ValueError("BaselineBenchmarkRun cases must be a non-empty tuple")
        if any(not isinstance(case, BaselineCaseRun) for case in self.cases):
            raise ValueError("BaselineBenchmarkRun cases must contain BaselineCaseRun values")
        case_ids = [case.case_id for case in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("BaselineBenchmarkRun case IDs must be unique")
        if not isinstance(self.evaluation, BenchmarkEvaluation):
            raise ValueError(
                "BaselineBenchmarkRun evaluation must be a BenchmarkEvaluation"
            )
        expected_evaluations = tuple(case.evaluation for case in self.cases)
        if self.evaluation.cases != expected_evaluations:
            raise ValueError(
                "BaselineBenchmarkRun evaluation cases must match case run evaluations"
            )
        if not isinstance(self.output_dir, Path):
            raise ValueError("BaselineBenchmarkRun output_dir must be a Path")
        if not isinstance(self.summary_path, Path):
            raise ValueError("BaselineBenchmarkRun summary_path must be a Path")

    @property
    def total_duration_seconds(self) -> float:
        """Return summed Codex wall-clock duration across cases."""
        return sum(case.codex_run.duration_seconds for case in self.cases)

    @property
    def timed_out_cases(self) -> tuple[str, ...]:
        """Return timed-out case IDs in experiment order."""
        return tuple(case.case_id for case in self.cases if case.codex_run.timed_out)

    @property
    def nonzero_exit_cases(self) -> tuple[str, ...]:
        """Return nonzero, non-timeout Codex exit case IDs in order."""
        return tuple(
            case.case_id
            for case in self.cases
            if case.codex_run.returncode is not None
            and case.codex_run.returncode != 0
        )


def _positive_timeout(value: object, name: str) -> float:
    """Validate a positive finite timeout without coercing booleans."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{name} must be a positive finite number")
    return value


def _is_within(path: Path, parent: Path) -> bool:
    """Return whether path equals or is below parent."""
    return path == parent or parent in path.parents


def _prepare_output_dir(output_dir: Path, case_dirs: tuple[Path, ...]) -> Path:
    """Validate output isolation and create an empty experiment directory."""
    if output_dir.is_symlink():
        raise ValueError(f"Output directory must not be a symlink: {output_dir}")
    resolved = output_dir.resolve()
    for case_dir in case_dirs:
        case_root = case_dir.resolve()
        if _is_within(resolved, case_root):
            raise ValueError("Output directory must not be equal to or inside a case")
        if _is_within(case_root, resolved):
            raise ValueError("Case directory must not be inside output directory")
    if output_dir.exists():
        if not output_dir.is_dir():
            raise ValueError(f"Output path is not a directory: {output_dir}")
        if any(output_dir.iterdir()):
            raise ValueError(f"Output directory is not empty: {output_dir}")
    else:
        output_dir.mkdir(parents=True)
    return output_dir.resolve()


def _assert_public_workspace(workspace: Path) -> None:
    """Require exactly the expected public inputs before solver execution."""
    names = {path.name for path in workspace.iterdir()}
    if names != {"task.md", "evidence", "repo"}:
        raise RuntimeError(
            f"Prepared solver workspace has unexpected top-level inputs: {sorted(names)!r}"
        )
    if not (workspace / "task.md").is_file():
        raise RuntimeError("Prepared solver workspace is missing task.md")
    if not (workspace / "evidence").is_dir() or not (workspace / "repo").is_dir():
        raise RuntimeError("Prepared solver workspace is missing evidence/ or repo/")
    if (workspace / "hidden").exists() or list(workspace.rglob("ground_truth.json")):
        raise RuntimeError("Prepared solver workspace contains private benchmark material")
    if (workspace / "evidencepatch_result.json").exists():
        raise RuntimeError("Prepared solver workspace already contains a solver result")


def _reject_workspace_symlinks(workspace: Path) -> None:
    """Reject every symlink before persisting a solver workspace."""
    for current, directories, files in os.walk(workspace, followlinks=False):
        current_path = Path(current)
        for name in directories + files:
            path = current_path / name
            if path.is_symlink():
                raise RuntimeError(
                    f"Solver workspace cannot be safely persisted because it contains a symlink: {path}"
                )


def _write_json(path: Path, data: object) -> None:
    """Write deterministic JSON with a trailing newline."""
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_case_evaluation(path: Path, evaluation: CaseEvaluation) -> None:
    """Persist one ordered seven-check case evaluation."""
    _write_json(
        path,
        {
            "schema_version": 1,
            "case_id": evaluation.case_id,
            "verified_success": evaluation.passed,
            "checks": [
                {"name": check.name, "passed": check.passed, "detail": check.detail}
                for check in evaluation.checks
            ],
        },
    )


def _summary_data(run: BaselineBenchmarkRun) -> dict:
    """Build deterministic benchmark summary data without private truth."""
    return {
        "schema_version": 1,
        "experiment": "plain_codex_baseline",
        "model": run.model,
        "prompt_sha256": run.prompt_sha256,
        "total_cases": run.evaluation.total_cases,
        "verified_successes": run.evaluation.verified_successes,
        "verified_failures": run.evaluation.verified_failures,
        "vusr": run.evaluation.vusr,
        "total_duration_seconds": run.total_duration_seconds,
        "timed_out_cases": list(run.timed_out_cases),
        "nonzero_exit_cases": list(run.nonzero_exit_cases),
        "check_metrics": [
            {
                "name": metric.name,
                "passed_cases": metric.passed_cases,
                "total_cases": metric.total_cases,
                "rate": metric.rate,
            }
            for metric in run.evaluation.check_metrics
        ],
        "cases": [
            {
                "case_id": case.case_id,
                "verified_success": case.verified_success,
                "failed_checks": [
                    check.name for check in case.evaluation.failed_checks
                ],
                "codex_returncode": case.codex_run.returncode,
                "codex_timed_out": case.codex_run.timed_out,
                "duration_seconds": case.codex_run.duration_seconds,
            }
            for case in run.cases
        ],
    }


def run_baseline_benchmark(
    case_dirs: tuple[Path, ...],
    output_dir: Path,
    *,
    model: str = "gpt-5.6-sol",
    codex_timeout_seconds: float = 180.0,
    hidden_timeout_seconds: float = 30.0,
) -> BaselineBenchmarkRun:
    """Run the frozen plain-Codex configuration once per case and persist it."""
    if not isinstance(case_dirs, tuple) or not case_dirs:
        raise ValueError("case_dirs must be a non-empty tuple")
    if any(not isinstance(case_dir, Path) for case_dir in case_dirs):
        raise ValueError("case_dirs must contain Path values")
    if not isinstance(output_dir, Path):
        raise ValueError("output_dir must be a Path")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a non-empty string")
    _positive_timeout(codex_timeout_seconds, "codex_timeout_seconds")
    _positive_timeout(hidden_timeout_seconds, "hidden_timeout_seconds")

    for case_dir in case_dirs:
        validate_case(case_dir)
    case_ids = [case_dir.name for case_dir in case_dirs]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("case directory names must be unique")

    resolved_output = _prepare_output_dir(output_dir, case_dirs)
    prompt_sha256 = hashlib.sha256(BASELINE_PROMPT.encode("utf-8")).hexdigest()
    metadata_path = resolved_output / "experiment_metadata.json"
    _write_json(
        metadata_path,
        {
            "schema_version": 1,
            "experiment": "plain_codex_baseline",
            "model": model,
            "prompt_sha256": prompt_sha256,
            "case_ids": case_ids,
            "codex_timeout_seconds": codex_timeout_seconds,
            "hidden_timeout_seconds": hidden_timeout_seconds,
            "retry_policy": "none",
            "solver_invocations_per_case": 1,
            "web_search_enabled": False,
            "human_feedback_during_run": False,
        },
    )

    case_runs: list[BaselineCaseRun] = []
    for case_dir, case_id in zip(case_dirs, case_ids, strict=True):
        case_output = resolved_output / case_id
        case_output.mkdir()
        with tempfile.TemporaryDirectory(prefix=f"evidencepatch-{case_id}-") as temporary:
            workspace = prepare_case_workspace(
                case_dir, Path(temporary) / "workspace"
            )
            _assert_public_workspace(workspace)
            codex_run = run_codex(
                workspace,
                case_output / "codex",
                BASELINE_PROMPT,
                model=model,
                timeout_seconds=codex_timeout_seconds,
            )
            evaluation = evaluate_case(
                case_dir,
                workspace,
                hidden_timeout_seconds=hidden_timeout_seconds,
            )
            _reject_workspace_symlinks(workspace)
            workspace_snapshot = case_output / "workspace"
            shutil.copytree(workspace, workspace_snapshot)

        evaluation_path = case_output / "evaluation.json"
        _write_case_evaluation(evaluation_path, evaluation)
        case_runs.append(
            BaselineCaseRun(
                case_id=case_id,
                codex_run=codex_run,
                evaluation=evaluation,
                workspace_snapshot=workspace_snapshot,
                evaluation_path=evaluation_path,
            )
        )

    aggregate = aggregate_case_evaluations(
        tuple(case.evaluation for case in case_runs)
    )
    summary_path = resolved_output / "benchmark_summary.json"
    run = BaselineBenchmarkRun(
        model=model,
        prompt_sha256=prompt_sha256,
        cases=tuple(case_runs),
        evaluation=aggregate,
        output_dir=resolved_output,
        summary_path=summary_path,
    )
    _write_json(summary_path, _summary_data(run))
    return run
