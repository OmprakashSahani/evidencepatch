from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.benchmark_evaluation import (
    BenchmarkEvaluation,
    CheckMetric,
    aggregate_case_evaluations,
)
from evidencepatch.evaluation_types import CaseEvaluation, EvaluationCheck


CHECK_NAMES = (
    "action_correct",
    "evidence_ids_correct",
    "human_review_correct",
    "declared_changes_match_actual",
    "production_impact_correct",
    "no_unexpected_repository_changes",
    "hidden_behavior_passed",
)


def _case(case_id, failed=(), names=CHECK_NAMES):
    return CaseEvaluation(
        case_id=case_id,
        checks=tuple(
            EvaluationCheck(name, name not in failed, f"Detail for {name}")
            for name in names
        ),
    )


def test_all_cases_successful():
    evaluation = aggregate_case_evaluations(
        (_case("case_01"), _case("case_02"), _case("case_03"))
    )

    assert evaluation.total_cases == 3
    assert evaluation.verified_successes == 3
    assert evaluation.verified_failures == 0
    assert evaluation.vusr == 1.0
    assert all(metric.passed_cases == 3 for metric in evaluation.check_metrics)
    assert all(metric.rate == 1.0 for metric in evaluation.check_metrics)


def test_vusr_is_strict_complete_case_success_rate():
    evaluation = aggregate_case_evaluations(
        (
            _case("case_01"),
            _case("case_02", {"hidden_behavior_passed"}),
            _case("case_03", {"action_correct"}),
        )
    )

    assert evaluation.verified_successes == 1
    assert evaluation.verified_failures == 2
    assert evaluation.vusr == 1 / 3


def test_secondary_check_rates_are_position_specific():
    evaluation = aggregate_case_evaluations(
        (
            _case("case_01"),
            _case("case_02", {"hidden_behavior_passed"}),
            _case("case_03", {"action_correct"}),
        )
    )

    action = evaluation.get_check_metric("action_correct")
    hidden = evaluation.get_check_metric("hidden_behavior_passed")
    evidence = evaluation.get_check_metric("evidence_ids_correct")
    assert (action.passed_cases, action.rate) == (2, 2 / 3)
    assert (hidden.passed_cases, hidden.rate) == (2, 2 / 3)
    assert (evidence.passed_cases, evidence.rate) == (3, 1.0)


def test_successful_cases_preserve_input_order():
    first = _case("case_03")
    failed = _case("case_01", {"action_correct"})
    last = _case("case_02")
    evaluation = aggregate_case_evaluations((first, failed, last))

    assert evaluation.successful_cases == (first, last)


def test_failed_cases_preserve_input_order():
    first = _case("case_03", {"action_correct"})
    passed = _case("case_01")
    last = _case("case_02", {"hidden_behavior_passed"})
    evaluation = aggregate_case_evaluations((first, passed, last))

    assert evaluation.failed_cases == (first, last)


def test_get_check_metric_finds_metric():
    evaluation = aggregate_case_evaluations((_case("case_01"),))

    assert evaluation.get_check_metric("action_correct") is evaluation.check_metrics[0]


def test_get_check_metric_rejects_unknown_name():
    evaluation = aggregate_case_evaluations((_case("case_01"),))

    with pytest.raises(KeyError, match="No benchmark check metric named 'missing'"):
        evaluation.get_check_metric("missing")


def test_empty_evaluation_tuple_is_rejected():
    with pytest.raises(ValueError, match="non-empty tuple"):
        aggregate_case_evaluations(())


def test_duplicate_case_ids_are_rejected():
    with pytest.raises(ValueError, match="case IDs.*unique"):
        aggregate_case_evaluations((_case("same"), _case("same")))


def test_mismatched_check_names_are_rejected():
    changed_names = CHECK_NAMES[:-1] + ("something_else",)

    with pytest.raises(ValueError, match="identical check names"):
        aggregate_case_evaluations(
            (_case("case_01"), _case("case_02", names=changed_names))
        )


def test_mismatched_check_order_is_rejected():
    changed_order = CHECK_NAMES[1:] + CHECK_NAMES[:1]

    with pytest.raises(ValueError, match="same order"):
        aggregate_case_evaluations(
            (_case("case_01"), _case("case_02", names=changed_order))
        )


def test_benchmark_evaluation_rejects_inconsistent_metric_names():
    case = _case("case_01")
    metrics = tuple(CheckMetric(name, 1, 1) for name in CHECK_NAMES[:-1]) + (
        CheckMetric("different", 1, 1),
    )

    with pytest.raises(ValueError, match="must match case check order"):
        BenchmarkEvaluation((case,), metrics)


def test_benchmark_evaluation_rejects_duplicate_metric_names():
    case = _case("case_01")
    metrics = tuple(CheckMetric(name, 1, 1) for name in CHECK_NAMES[:-1]) + (
        CheckMetric(CHECK_NAMES[0], 1, 1),
    )

    with pytest.raises(ValueError, match="metric names.*unique"):
        BenchmarkEvaluation((case,), metrics)


@pytest.mark.parametrize(
    ("name", "passed", "total", "message"),
    [
        (" ", 0, 1, "name.*non-empty"),
        ("check", -1, 1, "passed_cases.*non-negative"),
        ("check", 0, 0, "total_cases.*positive"),
        ("check", 2, 1, "must not exceed"),
        ("check", True, 1, "passed_cases.*non-negative"),
        ("check", 1, True, "total_cases.*positive"),
    ],
)
def test_check_metric_rejects_invalid_values(name, passed, total, message):
    with pytest.raises(ValueError, match=message):
        CheckMetric(name, passed, total)


def test_dataclasses_are_immutable():
    metric = CheckMetric("check", 1, 1)
    evaluation = aggregate_case_evaluations((_case("case_01"),))

    with pytest.raises(FrozenInstanceError):
        metric.passed_cases = 0
    with pytest.raises(FrozenInstanceError):
        evaluation.cases = ()
