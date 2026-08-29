import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.case_evaluator import evaluate_case
from evidencepatch.result_contract import RESULT_FILENAME
from evidencepatch.workspace import prepare_case_workspace


CASES = PROJECT_ROOT / "benchmark" / "cases"
CHECK_NAMES = (
    "action_correct",
    "evidence_ids_correct",
    "human_review_correct",
    "declared_changes_match_actual",
    "production_impact_correct",
    "no_unexpected_repository_changes",
    "hidden_behavior_passed",
)


def _stage(tmp_path, case_id):
    case = CASES / case_id
    workspace = prepare_case_workspace(case, tmp_path / "solver_workspace")
    return case, workspace


def _write_result(workspace, action, changed_files, evidence_ids):
    data = {
        "schema_version": 1,
        "action": action,
        "changed_files": changed_files,
        "evidence_ids": evidence_ids,
        "human_review_required": True,
        "summary": "Evaluated the synthetic evidence and repository.",
    }
    (workspace / RESULT_FILENAME).write_text(json.dumps(data))


def _patch_case_01(workspace):
    (workspace / "repo" / "medication_rules" / "velunex.py").write_text(
        "def is_velunex_allowed(patient: dict) -> bool:\n"
        "    if patient.get(\"velunex_allergy\", False):\n"
        "        return False\n"
        "    if patient.get(\"marker_q\", 0) >= 70:\n"
        "        return False\n"
        "    return True\n"
    )


def test_correct_case_01_patch_passes_all_seven_checks(tmp_path):
    case, workspace = _stage(tmp_path, "case_01")
    _patch_case_01(workspace)
    _write_result(
        workspace,
        "PATCH",
        ["medication_rules/velunex.py"],
        ["SYN-VELUNEX-2026-V2"],
    )

    evaluation = evaluate_case(case, workspace)

    assert evaluation.passed is True
    assert tuple(check.name for check in evaluation.checks) == CHECK_NAMES


def test_static_correct_but_behavior_wrong_fails_only_hidden_check(tmp_path):
    case, workspace = _stage(tmp_path, "case_01")
    rule = workspace / "repo" / "medication_rules" / "velunex.py"
    rule.write_text(rule.read_text() + "\n# harmless static change\n")
    _write_result(
        workspace,
        "PATCH",
        ["medication_rules/velunex.py"],
        ["SYN-VELUNEX-2026-V2"],
    )

    evaluation = evaluate_case(case, workspace)

    assert all(check.passed for check in evaluation.checks[:6])
    assert evaluation.get_check("hidden_behavior_passed").passed is False
    assert evaluation.passed is False


def test_correct_case_10_escalate_passes_all_checks(tmp_path):
    case, workspace = _stage(tmp_path, "case_10")
    _write_result(
        workspace,
        "ESCALATE",
        [],
        ["SYN-ZORAVEL-GUIDE-2026-V4", "SYN-ZORAVEL-STUDY-2026-08"],
    )

    assert evaluate_case(case, workspace).passed is True


def test_correct_case_12_no_patch_passes_all_checks(tmp_path):
    case, workspace = _stage(tmp_path, "case_12")
    _write_result(
        workspace,
        "NO_PATCH",
        [],
        ["SYN-PRAXENOR-GUIDE-2026-V1", "SYN-PRAXENOR-GUIDE-2026-V2"],
    )

    assert evaluate_case(case, workspace).passed is True


def test_wrong_case_10_action_fails_despite_correct_behavior(tmp_path):
    case, workspace = _stage(tmp_path, "case_10")
    _write_result(
        workspace,
        "NO_PATCH",
        [],
        ["SYN-ZORAVEL-GUIDE-2026-V4", "SYN-ZORAVEL-STUDY-2026-08"],
    )

    evaluation = evaluate_case(case, workspace)

    assert evaluation.get_check("action_correct").passed is False
    assert evaluation.get_check("hidden_behavior_passed").passed is True
    assert evaluation.passed is False


def test_missing_result_scores_static_failure_but_hidden_can_pass(tmp_path):
    case, workspace = _stage(tmp_path, "case_12")

    evaluation = evaluate_case(case, workspace)

    assert all(not check.passed for check in evaluation.checks[:6])
    assert evaluation.get_check("hidden_behavior_passed").passed is True
    assert evaluation.passed is False


def test_malformed_result_scores_static_failure_but_hidden_can_pass(tmp_path):
    case, workspace = _stage(tmp_path, "case_12")
    (workspace / RESULT_FILENAME).write_text("{invalid JSON")

    evaluation = evaluate_case(case, workspace)

    assert all(not check.passed for check in evaluation.checks[:6])
    assert evaluation.get_check("hidden_behavior_passed").passed is True
    assert evaluation.passed is False


def test_unsafe_target_repo_fails_without_crashing(tmp_path):
    case, workspace = _stage(tmp_path, "case_12")
    _write_result(
        workspace,
        "NO_PATCH",
        [],
        ["SYN-PRAXENOR-GUIDE-2026-V1", "SYN-PRAXENOR-GUIDE-2026-V2"],
    )
    external = tmp_path / "external.py"
    external.write_text("EXTERNAL = True\n")
    (workspace / "repo" / "linked.py").symlink_to(external)

    evaluation = evaluate_case(case, workspace)

    assert evaluation.passed is False
    assert evaluation.get_check("hidden_behavior_passed").passed is False


def test_complete_check_order_is_exact(tmp_path):
    case, workspace = _stage(tmp_path, "case_12")
    _write_result(
        workspace,
        "NO_PATCH",
        [],
        ["SYN-PRAXENOR-GUIDE-2026-V1", "SYN-PRAXENOR-GUIDE-2026-V2"],
    )

    evaluation = evaluate_case(case, workspace)

    assert tuple(check.name for check in evaluation.checks) == CHECK_NAMES
