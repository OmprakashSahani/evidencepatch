from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.hidden_behavior import HiddenBehaviorResult, run_hidden_behavior
from evidencepatch.workspace import prepare_case_workspace


CASES = PROJECT_ROOT / "benchmark" / "cases"


def _stage(tmp_path, case_id):
    case = CASES / case_id
    workspace = prepare_case_workspace(case, tmp_path / "solver_workspace")
    return case, workspace / "repo"


def _patch_case_01(target_repo):
    (target_repo / "medication_rules" / "velunex.py").write_text(
        "def is_velunex_allowed(patient: dict) -> bool:\n"
        "    if patient.get(\"velunex_allergy\", False):\n"
        "        return False\n"
        "    if patient.get(\"marker_q\", 0) >= 70:\n"
        "        return False\n"
        "    return True\n"
    )


def test_case_12_staged_repo_passes_hidden_behavior(tmp_path):
    case, target_repo = _stage(tmp_path, "case_12")

    result = run_hidden_behavior(case, target_repo)

    assert result.passed is True
    assert result.tests_total == 7
    assert result.tests_passed == 7
    assert result.tests_failed == 0
    assert result.tests_errors == 0


def test_case_01_old_staged_repo_has_expected_failures(tmp_path):
    case, target_repo = _stage(tmp_path, "case_01")

    result = run_hidden_behavior(case, target_repo)

    assert result.passed is False
    assert result.tests_total == 4
    assert result.tests_passed == 2
    assert result.tests_failed == 2


def test_patched_case_01_passes_hidden_behavior(tmp_path):
    case, target_repo = _stage(tmp_path, "case_01")
    _patch_case_01(target_repo)

    result = run_hidden_behavior(case, target_repo)

    assert result.passed is True
    assert result.tests_total == 4
    assert result.tests_passed == 4


def test_nested_target_symlink_is_rejected_before_execution(tmp_path):
    case, target_repo = _stage(tmp_path, "case_12")
    external = tmp_path / "external.py"
    external.write_text("EXTERNAL = True\n")
    (target_repo / "linked.py").symlink_to(external)

    with pytest.raises(ValueError, match="symlinks"):
        run_hidden_behavior(case, target_repo)


@pytest.mark.parametrize("invalid_timeout", [0, -1, True])
def test_invalid_timeout_is_rejected(tmp_path, invalid_timeout):
    case, target_repo = _stage(tmp_path, "case_12")

    with pytest.raises(ValueError, match="timeout_seconds"):
        run_hidden_behavior(case, target_repo, timeout_seconds=invalid_timeout)


@pytest.mark.parametrize("invalid_passed", [1, 0, "true", None])
def test_hidden_behavior_result_rejects_non_boolean_passed(invalid_passed):
    with pytest.raises(ValueError, match="passed.*boolean"):
        HiddenBehaviorResult(invalid_passed, 0, 0, 0, 0, 0, None, "detail")


def test_hidden_behavior_result_rejects_inconsistent_counts():
    with pytest.raises(ValueError, match="sum to tests_total"):
        HiddenBehaviorResult(False, 2, 1, 0, 0, 0, 1, "detail")
