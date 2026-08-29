from pathlib import Path
import subprocess
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import evidencepatch.hidden_behavior as hidden_behavior_module
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


def test_resolved_pytest_executable_is_used(tmp_path, monkeypatch):
    case, target_repo = _stage(tmp_path, "case_12")
    observed = {}
    monkeypatch.setattr(hidden_behavior_module.shutil, "which", lambda name: "/fake/bin/pytest")

    def fake_run(command, **kwargs):
        observed["command"] = command
        junit_argument = next(
            argument for argument in command if argument.startswith("--junitxml=")
        )
        report = Path(junit_argument.split("=", 1)[1])
        report.write_text(
            '<testsuite tests="1" failures="0" errors="0" skipped="0" />'
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(hidden_behavior_module.subprocess, "run", fake_run)

    result = run_hidden_behavior(case, target_repo)

    assert observed["command"][0] == "/fake/bin/pytest"
    assert "-m" not in observed["command"]
    assert "pytest" not in observed["command"][1:]
    assert result.passed is True
    assert result.tests_total == 1


def test_missing_pytest_executable_is_infrastructure_error(tmp_path, monkeypatch):
    case, target_repo = _stage(tmp_path, "case_12")
    monkeypatch.setattr(hidden_behavior_module.shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError, match="environment.*pytest executable"):
        run_hidden_behavior(case, target_repo)


def test_missing_junit_includes_stderr_diagnostic(tmp_path, monkeypatch):
    case, target_repo = _stage(tmp_path, "case_12")
    monkeypatch.setattr(hidden_behavior_module.shutil, "which", lambda name: "/fake/bin/pytest")
    monkeypatch.setattr(
        hidden_behavior_module.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="synthetic pytest startup failure",
        ),
    )

    result = run_hidden_behavior(case, target_repo)

    assert result.passed is False
    assert result.tests_total == 0
    assert result.returncode == 1
    assert "synthetic pytest startup failure" in result.detail


def test_missing_junit_diagnostic_is_bounded(tmp_path, monkeypatch):
    case, target_repo = _stage(tmp_path, "case_12")
    monkeypatch.setattr(hidden_behavior_module.shutil, "which", lambda name: "/fake/bin/pytest")
    monkeypatch.setattr(
        hidden_behavior_module.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="x" * 5000,
        ),
    )

    result = run_hidden_behavior(case, target_repo)

    prefix = "Hidden pytest JUnit report was not created; subprocess diagnostic: "
    assert result.detail.startswith(prefix)
    assert len(result.detail) <= len(prefix) + 400
    assert len(result.detail) < 1000
