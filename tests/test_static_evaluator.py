import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.result_contract import RESULT_FILENAME
from evidencepatch.static_evaluator import evaluate_static_case
from evidencepatch.workspace import prepare_case_workspace


CASES = PROJECT_ROOT / "benchmark" / "cases"


def _workspace(tmp_path, case_id):
    case = CASES / case_id
    workspace = prepare_case_workspace(case, tmp_path / "solver_workspace")
    return case, workspace


def _write_result(
    workspace,
    *,
    action,
    changed_files,
    evidence_ids,
    human_review_required=True,
):
    data = {
        "schema_version": 1,
        "action": action,
        "changed_files": changed_files,
        "evidence_ids": evidence_ids,
        "human_review_required": human_review_required,
        "summary": "Evaluated the synthetic evidence and repository impact.",
    }
    (workspace / RESULT_FILENAME).write_text(json.dumps(data))


def _patch_case_01(workspace):
    rule = workspace / "repo" / "medication_rules" / "velunex.py"
    rule.write_text(
        "def is_velunex_allowed(patient: dict) -> bool:\n"
        "    if patient.get(\"velunex_allergy\", False):\n"
        "        return False\n"
        "    if patient.get(\"marker_q\", 0) >= 70:\n"
        "        return False\n"
        "    return True\n"
    )


def _checks(evaluation):
    return {check.name: check.passed for check in evaluation.checks}


def test_correct_case_01_patch_passes_all_checks(tmp_path):
    case, workspace = _workspace(tmp_path, "case_01")
    _patch_case_01(workspace)
    _write_result(
        workspace,
        action="PATCH",
        changed_files=["medication_rules/velunex.py"],
        evidence_ids=["SYN-VELUNEX-2026-V2"],
    )

    evaluation = evaluate_static_case(case, workspace)

    assert evaluation.passed is True
    assert tuple(check.name for check in evaluation.checks) == (
        "action_correct",
        "evidence_ids_correct",
        "human_review_correct",
        "declared_changes_match_actual",
        "production_impact_correct",
        "no_unexpected_repository_changes",
    )


def test_correct_case_10_escalate_passes_all_checks(tmp_path):
    case, workspace = _workspace(tmp_path, "case_10")
    _write_result(
        workspace,
        action="ESCALATE",
        changed_files=[],
        evidence_ids=["SYN-ZORAVEL-GUIDE-2026-V4", "SYN-ZORAVEL-STUDY-2026-08"],
    )

    assert evaluate_static_case(case, workspace).passed is True


def test_correct_case_12_no_patch_passes_all_checks(tmp_path):
    case, workspace = _workspace(tmp_path, "case_12")
    _write_result(
        workspace,
        action="NO_PATCH",
        changed_files=[],
        evidence_ids=["SYN-PRAXENOR-GUIDE-2026-V1", "SYN-PRAXENOR-GUIDE-2026-V2"],
        human_review_required=False,
    )

    assert evaluate_static_case(case, workspace).passed is True


def test_wrong_action_only_fails_action_check(tmp_path):
    case, workspace = _workspace(tmp_path, "case_12")
    _write_result(
        workspace,
        action="ESCALATE",
        changed_files=[],
        evidence_ids=["SYN-PRAXENOR-GUIDE-2026-V1", "SYN-PRAXENOR-GUIDE-2026-V2"],
        human_review_required=False,
    )

    checks = _checks(evaluate_static_case(case, workspace))

    assert checks["action_correct"] is False
    assert all(passed for name, passed in checks.items() if name != "action_correct")


def test_evidence_order_does_not_matter(tmp_path):
    case, workspace = _workspace(tmp_path, "case_10")
    _write_result(
        workspace,
        action="ESCALATE",
        changed_files=[],
        evidence_ids=["SYN-ZORAVEL-STUDY-2026-08", "SYN-ZORAVEL-GUIDE-2026-V4"],
    )

    assert evaluate_static_case(case, workspace).get_check("evidence_ids_correct").passed


def test_missing_evidence_id_fails_evidence_check(tmp_path):
    case, workspace = _workspace(tmp_path, "case_10")
    _write_result(
        workspace,
        action="ESCALATE",
        changed_files=[],
        evidence_ids=["SYN-ZORAVEL-GUIDE-2026-V4"],
    )

    assert not evaluate_static_case(case, workspace).get_check(
        "evidence_ids_correct"
    ).passed


def test_unexpected_evidence_id_fails_evidence_check(tmp_path):
    case, workspace = _workspace(tmp_path, "case_10")
    _write_result(
        workspace,
        action="ESCALATE",
        changed_files=[],
        evidence_ids=[
            "SYN-ZORAVEL-GUIDE-2026-V4",
            "SYN-ZORAVEL-STUDY-2026-08",
            "SYN-UNEXPECTED",
        ],
    )

    assert not evaluate_static_case(case, workspace).get_check(
        "evidence_ids_correct"
    ).passed


def test_wrong_human_review_fails_review_check(tmp_path):
    case, workspace = _workspace(tmp_path, "case_12")
    _write_result(
        workspace,
        action="NO_PATCH",
        changed_files=[],
        evidence_ids=["SYN-PRAXENOR-GUIDE-2026-V1", "SYN-PRAXENOR-GUIDE-2026-V2"],
        human_review_required=True,
    )

    assert not evaluate_static_case(case, workspace).get_check(
        "human_review_correct"
    ).passed


def test_declared_changes_can_disagree_while_production_impact_passes(tmp_path):
    case, workspace = _workspace(tmp_path, "case_01")
    _patch_case_01(workspace)
    _write_result(
        workspace,
        action="PATCH",
        changed_files=["tests/test_velunex.py"],
        evidence_ids=["SYN-VELUNEX-2026-V2"],
    )

    checks = _checks(evaluate_static_case(case, workspace))

    assert checks["declared_changes_match_actual"] is False
    assert checks["production_impact_correct"] is True


def test_patch_changing_only_tests_misses_production_impact(tmp_path):
    case, workspace = _workspace(tmp_path, "case_01")
    test_file = workspace / "repo" / "tests" / "test_velunex.py"
    test_file.write_text(test_file.read_text() + "\n# staged regression\n")
    _write_result(
        workspace,
        action="PATCH",
        changed_files=["tests/test_velunex.py"],
        evidence_ids=["SYN-VELUNEX-2026-V2"],
    )

    checks = _checks(evaluate_static_case(case, workspace))

    assert checks["production_impact_correct"] is False
    assert checks["no_unexpected_repository_changes"] is True


def test_patch_with_expected_production_and_visible_test_passes(tmp_path):
    case, workspace = _workspace(tmp_path, "case_01")
    _patch_case_01(workspace)
    test_file = workspace / "repo" / "tests" / "test_velunex.py"
    test_file.write_text(test_file.read_text() + "\n# staged regression\n")
    _write_result(
        workspace,
        action="PATCH",
        changed_files=["medication_rules/velunex.py", "tests/test_velunex.py"],
        evidence_ids=["SYN-VELUNEX-2026-V2"],
    )

    assert evaluate_static_case(case, workspace).passed is True


def test_unexpected_extra_production_file_is_rejected_separately(tmp_path):
    case, workspace = _workspace(tmp_path, "case_01")
    _patch_case_01(workspace)
    extra = workspace / "repo" / "medication_rules" / "unrelated.py"
    extra.write_text("UNRELATED = True\n")
    _write_result(
        workspace,
        action="PATCH",
        changed_files=["medication_rules/velunex.py", "medication_rules/unrelated.py"],
        evidence_ids=["SYN-VELUNEX-2026-V2"],
    )

    checks = _checks(evaluate_static_case(case, workspace))

    assert checks["production_impact_correct"] is True
    assert checks["no_unexpected_repository_changes"] is False


def test_unexpected_configuration_file_is_rejected(tmp_path):
    case, workspace = _workspace(tmp_path, "case_01")
    _patch_case_01(workspace)
    (workspace / "repo" / "config.json").write_text("{}\n")
    _write_result(
        workspace,
        action="PATCH",
        changed_files=["medication_rules/velunex.py", "config.json"],
        evidence_ids=["SYN-VELUNEX-2026-V2"],
    )

    assert not evaluate_static_case(case, workspace).get_check(
        "no_unexpected_repository_changes"
    ).passed


def test_deleted_test_is_rejected(tmp_path):
    case, workspace = _workspace(tmp_path, "case_01")
    _patch_case_01(workspace)
    (workspace / "repo" / "tests" / "test_velunex.py").unlink()
    _write_result(
        workspace,
        action="PATCH",
        changed_files=["medication_rules/velunex.py", "tests/test_velunex.py"],
        evidence_ids=["SYN-VELUNEX-2026-V2"],
    )

    checks = _checks(evaluate_static_case(case, workspace))

    assert checks["declared_changes_match_actual"] is True
    assert checks["no_unexpected_repository_changes"] is False


def test_no_patch_repository_mutation_is_rejected(tmp_path):
    case, workspace = _workspace(tmp_path, "case_12")
    test_file = workspace / "repo" / "tests" / "test_praxenor.py"
    test_file.write_text(test_file.read_text() + "\n# tampered\n")
    _write_result(
        workspace,
        action="NO_PATCH",
        changed_files=[],
        evidence_ids=["SYN-PRAXENOR-GUIDE-2026-V1", "SYN-PRAXENOR-GUIDE-2026-V2"],
        human_review_required=False,
    )

    checks = _checks(evaluate_static_case(case, workspace))

    assert checks["declared_changes_match_actual"] is False
    assert checks["production_impact_correct"] is True
    assert checks["no_unexpected_repository_changes"] is False


def test_multifile_case_requires_every_expected_production_file(tmp_path):
    case, workspace = _workspace(tmp_path, "case_09")
    initiation = workspace / "repo" / "medication_rules" / "initiation.py"
    initiation.write_text(initiation.read_text() + "\n# staged change\n")
    _write_result(
        workspace,
        action="PATCH",
        changed_files=["medication_rules/initiation.py"],
        evidence_ids=["SYN-AVENORIL-2026-V9"],
    )

    assert not evaluate_static_case(case, workspace).get_check(
        "production_impact_correct"
    ).passed
