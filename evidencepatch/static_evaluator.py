"""Static per-case evaluation without behavioral test execution."""

import json
from pathlib import Path, PurePosixPath

from evidencepatch.case_validation import validate_case
from evidencepatch.evaluation_types import CaseEvaluation, EvaluationCheck
from evidencepatch.repo_diff import RepositoryDiff, compare_repositories
from evidencepatch.result_contract import RESULT_FILENAME, load_solver_result


def _is_test_path(path: str) -> bool:
    """Return whether a normalized repo-relative path is below tests/."""
    parts = PurePosixPath(path).parts
    return bool(parts) and parts[0] == "tests"


def _sorted(values) -> list[str]:
    """Return deterministic lexical ordering for detail output."""
    return sorted(values)


def _production_impact_check(
    expected_action: str,
    expected_production: set[str],
    repository_diff: RepositoryDiff,
) -> EvaluationCheck:
    """Evaluate whether required production files received the right impact."""
    modified = set(repository_diff.modified_files)
    actual_non_test = {
        path for path in repository_diff.changed_files if not _is_test_path(path)
    }
    if expected_action == "PATCH":
        missing_modified = expected_production - modified
        passed = not missing_modified
    else:
        missing_modified = set()
        passed = not actual_non_test
    detail = (
        f"expected_action={expected_action!r}; "
        f"expected_production_files={_sorted(expected_production)!r}; "
        f"modified_files={_sorted(modified)!r}; "
        f"actual_non_test_changes={_sorted(actual_non_test)!r}; "
        f"expected_files_not_modified={_sorted(missing_modified)!r}"
    )
    return EvaluationCheck("production_impact_correct", passed, detail)


def _unexpected_changes_check(
    expected_action: str,
    expected_production: set[str],
    repository_diff: RepositoryDiff,
) -> EvaluationCheck:
    """Evaluate whether actual changes stay within the allowed case scope."""
    changed = set(repository_diff.changed_files)
    deleted = set(repository_diff.deleted_files)
    if expected_action == "PATCH":
        unexpected = {
            path
            for path in changed
            if path not in expected_production and not _is_test_path(path)
        }
        passed = not unexpected and not deleted
    else:
        unexpected = changed
        passed = repository_diff.is_clean
    detail = (
        f"expected_action={expected_action!r}; "
        f"allowed_production_files={_sorted(expected_production)!r}; "
        f"unexpected_paths={_sorted(unexpected)!r}; "
        f"deleted_paths={_sorted(deleted)!r}"
    )
    return EvaluationCheck("no_unexpected_repository_changes", passed, detail)


def evaluate_static_case(case_dir: Path, solver_workspace: Path) -> CaseEvaluation:
    """Evaluate solver claims and filesystem impact against private case truth."""
    validate_case(case_dir)
    if solver_workspace.is_symlink():
        raise ValueError(f"Solver workspace must not be a symlink: {solver_workspace}")
    if not solver_workspace.exists():
        raise FileNotFoundError(f"Solver workspace does not exist: {solver_workspace}")
    if not solver_workspace.is_dir():
        raise ValueError(f"Solver workspace is not a directory: {solver_workspace}")

    solver_result = load_solver_result(solver_workspace / RESULT_FILENAME)
    repository_diff = compare_repositories(
        case_dir / "repo", solver_workspace / "repo"
    )
    ground_truth_path = case_dir / "hidden" / "ground_truth.json"
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))

    expected_action = ground_truth["expected_action"]
    expected_evidence = set(ground_truth["required_evidence_ids"])
    actual_evidence = set(solver_result.evidence_ids)
    missing_evidence = expected_evidence - actual_evidence
    unexpected_evidence = actual_evidence - expected_evidence
    expected_review = ground_truth["requires_human_review"]
    expected_production = set(ground_truth["expected_impacted_production_files"])

    declared = set(solver_result.changed_files)
    actual = set(repository_diff.changed_files)
    undeclared = actual - declared
    declared_not_actual = declared - actual

    checks = (
        EvaluationCheck(
            "action_correct",
            solver_result.action == expected_action,
            f"expected_action={expected_action!r}; actual_action={solver_result.action!r}",
        ),
        EvaluationCheck(
            "evidence_ids_correct",
            not missing_evidence and not unexpected_evidence,
            f"expected_ids={_sorted(expected_evidence)!r}; "
            f"actual_ids={_sorted(actual_evidence)!r}; "
            f"missing_ids={_sorted(missing_evidence)!r}; "
            f"unexpected_ids={_sorted(unexpected_evidence)!r}",
        ),
        EvaluationCheck(
            "human_review_correct",
            solver_result.human_review_required == expected_review,
            f"expected_human_review={expected_review!r}; "
            f"actual_human_review={solver_result.human_review_required!r}",
        ),
        EvaluationCheck(
            "declared_changes_match_actual",
            not undeclared and not declared_not_actual,
            f"declared_changes={_sorted(declared)!r}; "
            f"actual_changes={_sorted(actual)!r}; "
            f"undeclared_actual_changes={_sorted(undeclared)!r}; "
            f"declared_but_not_actual={_sorted(declared_not_actual)!r}",
        ),
        _production_impact_check(
            expected_action, expected_production, repository_diff
        ),
        _unexpected_changes_check(
            expected_action, expected_production, repository_diff
        ),
    )
    return CaseEvaluation(case_id=ground_truth["case_id"], checks=checks)
