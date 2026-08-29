"""Complete static and hidden-behavior evaluation for one case."""

from pathlib import Path

from evidencepatch.case_validation import validate_case
from evidencepatch.evaluation_types import CaseEvaluation, EvaluationCheck
from evidencepatch.hidden_behavior import HiddenBehaviorResult, run_hidden_behavior
from evidencepatch.static_evaluator import evaluate_static_case


_STATIC_CHECK_NAMES = (
    "action_correct",
    "evidence_ids_correct",
    "human_review_correct",
    "declared_changes_match_actual",
    "production_impact_correct",
    "no_unexpected_repository_changes",
)


def _bounded_error(prefix: str, error: Exception) -> str:
    """Create a compact deterministic diagnostic for an expected failure."""
    message = " ".join(str(error).split())
    if len(message) > 240:
        message = message[:237] + "..."
    return f"{prefix}: {type(error).__name__}: {message}"


def _hidden_check(result: HiddenBehaviorResult) -> EvaluationCheck:
    """Convert a hidden execution result into the seventh case check."""
    detail = (
        f"tests_total={result.tests_total}; tests_passed={result.tests_passed}; "
        f"tests_failed={result.tests_failed}; tests_errors={result.tests_errors}; "
        f"tests_skipped={result.tests_skipped}; returncode={result.returncode!r}; "
        f"detail={result.detail}"
    )
    return EvaluationCheck("hidden_behavior_passed", result.passed, detail)


def evaluate_case(
    case_dir: Path,
    solver_workspace: Path,
    *,
    hidden_timeout_seconds: float = 30.0,
) -> CaseEvaluation:
    """Evaluate one solver workspace statically and behaviorally."""
    validate_case(case_dir)

    try:
        static_evaluation = evaluate_static_case(case_dir, solver_workspace)
        static_checks = static_evaluation.checks
    except (FileNotFoundError, ValueError, OSError) as error:
        detail = _bounded_error(
            "Static evaluation unavailable because solver output was invalid", error
        )
        static_checks = tuple(
            EvaluationCheck(name, False, detail) for name in _STATIC_CHECK_NAMES
        )

    try:
        hidden_result = run_hidden_behavior(
            case_dir,
            solver_workspace / "repo",
            timeout_seconds=hidden_timeout_seconds,
        )
        hidden_check = _hidden_check(hidden_result)
    except (FileNotFoundError, ValueError, OSError) as error:
        detail = _bounded_error(
            "Hidden behavior unavailable because target repository was invalid", error
        )
        hidden_check = EvaluationCheck("hidden_behavior_passed", False, detail)

    return CaseEvaluation(
        case_id=case_dir.name,
        checks=static_checks + (hidden_check,),
    )
