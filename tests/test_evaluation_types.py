from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.evaluation_types import CaseEvaluation, EvaluationCheck


def _check(name, passed=True):
    return EvaluationCheck(name=name, passed=passed, detail=f"Detail for {name}")


def test_all_checks_pass():
    evaluation = CaseEvaluation("case_x", (_check("first"), _check("second")))

    assert evaluation.passed is True
    assert evaluation.failed_checks == ()


def test_one_failed_check_makes_case_fail():
    evaluation = CaseEvaluation("case_x", (_check("first"), _check("second", False)))

    assert evaluation.passed is False


def test_failed_checks_preserve_original_order():
    first = _check("first", False)
    middle = _check("middle", True)
    last = _check("last", False)
    evaluation = CaseEvaluation("case_x", (first, middle, last))

    assert evaluation.failed_checks == (first, last)


def test_get_check_finds_named_check():
    expected = _check("target")
    evaluation = CaseEvaluation("case_x", (_check("first"), expected))

    assert evaluation.get_check("target") is expected


def test_get_check_rejects_unknown_name():
    evaluation = CaseEvaluation("case_x", (_check("known"),))

    with pytest.raises(KeyError, match="No evaluation check named 'missing'"):
        evaluation.get_check("missing")


def test_empty_case_id_is_rejected():
    with pytest.raises(ValueError, match="case_id.*non-empty"):
        CaseEvaluation("  ", (_check("check"),))


def test_empty_checks_are_rejected():
    with pytest.raises(ValueError, match="checks.*non-empty"):
        CaseEvaluation("case_x", ())


def test_duplicate_check_names_are_rejected():
    with pytest.raises(ValueError, match="names.*unique"):
        CaseEvaluation("case_x", (_check("same"), _check("same")))


def test_empty_check_name_is_rejected():
    with pytest.raises(ValueError, match="name.*non-empty"):
        EvaluationCheck(" ", True, "detail")


@pytest.mark.parametrize("invalid_passed", [1, 0, "true", None])
def test_non_boolean_passed_is_rejected(invalid_passed):
    with pytest.raises(ValueError, match="passed.*boolean"):
        EvaluationCheck("check", invalid_passed, "detail")


def test_empty_detail_is_rejected():
    with pytest.raises(ValueError, match="detail.*non-empty"):
        EvaluationCheck("check", True, "  ")


def test_dataclasses_are_immutable():
    check = _check("check")
    evaluation = CaseEvaluation("case_x", (check,))

    with pytest.raises(FrozenInstanceError):
        check.passed = False
    with pytest.raises(FrozenInstanceError):
        evaluation.case_id = "different"
