import json
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.result_contract import (
    RESULT_SCHEMA_VERSION,
    SolverResult,
    load_solver_result,
    validate_solver_result,
)


def _valid_result(action="PATCH"):
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "action": action,
        "changed_files": (
            ["medication_rules/example.py", "tests/test_example.py"]
            if action == "PATCH"
            else []
        ),
        "evidence_ids": ["SYN-EXAMPLE-2026-V2"],
        "human_review_required": True,
        "summary": "Updated the affected medication rule and tests.",
    }


def test_valid_patch_result_uses_immutable_tuples():
    result = validate_solver_result(_valid_result())

    assert result == SolverResult(
        schema_version=1,
        action="PATCH",
        changed_files=("medication_rules/example.py", "tests/test_example.py"),
        evidence_ids=("SYN-EXAMPLE-2026-V2",),
        human_review_required=True,
        summary="Updated the affected medication rule and tests.",
    )


@pytest.mark.parametrize("action", ["NO_PATCH", "ESCALATE"])
def test_valid_non_patch_result(action):
    result = validate_solver_result(_valid_result(action))

    assert result.action == action
    assert result.changed_files == ()


def test_patch_requires_changed_file():
    data = _valid_result()
    data["changed_files"] = []

    with pytest.raises(ValueError, match="non-empty.*PATCH"):
        validate_solver_result(data)


@pytest.mark.parametrize("action", ["NO_PATCH", "ESCALATE"])
def test_non_patch_action_rejects_changed_files(action):
    data = _valid_result(action)
    data["changed_files"] = ["medication_rules/example.py"]

    with pytest.raises(ValueError, match=f"empty when action is {action}"):
        validate_solver_result(data)


def test_invalid_action_is_rejected():
    data = _valid_result()
    data["action"] = "IGNORE"

    with pytest.raises(ValueError, match="action"):
        validate_solver_result(data)


@pytest.mark.parametrize("version", [0, 2, "1", True])
def test_invalid_schema_version_is_rejected(version):
    data = _valid_result()
    data["schema_version"] = version

    with pytest.raises(ValueError, match="schema_version"):
        validate_solver_result(data)


def test_missing_required_field_is_rejected():
    data = _valid_result()
    del data["summary"]

    with pytest.raises(ValueError, match="missing.*summary"):
        validate_solver_result(data)


def test_unknown_field_is_rejected():
    data = _valid_result()
    data["unexpected"] = True

    with pytest.raises(ValueError, match="unknown.*unexpected"):
        validate_solver_result(data)


def test_duplicate_changed_files_are_rejected():
    data = _valid_result()
    data["changed_files"] = ["medication_rules/example.py"] * 2

    with pytest.raises(ValueError, match="changed_files.*duplicate"):
        validate_solver_result(data)


def test_duplicate_evidence_ids_are_rejected():
    data = _valid_result()
    data["evidence_ids"] = ["SYN-EXAMPLE"] * 2

    with pytest.raises(ValueError, match="evidence_ids.*duplicate"):
        validate_solver_result(data)


def test_empty_evidence_ids_are_rejected():
    data = _valid_result()
    data["evidence_ids"] = []

    with pytest.raises(ValueError, match="evidence_ids.*non-empty"):
        validate_solver_result(data)


def test_empty_summary_is_rejected():
    data = _valid_result()
    data["summary"] = "   "

    with pytest.raises(ValueError, match="summary.*non-empty"):
        validate_solver_result(data)


@pytest.mark.parametrize(
    "invalid_path",
    [
        "/absolute.py",
        "../outside.py",
        "medication_rules/../outside.py",
        "medication_rules\\rule.py",
        "repo/medication_rules/rule.py",
        ".",
        "",
    ],
)
def test_invalid_changed_path_is_rejected(invalid_path):
    data = _valid_result()
    data["changed_files"] = [invalid_path]

    with pytest.raises(ValueError, match="changed_files"):
        validate_solver_result(data)


def test_load_valid_json_file(tmp_path):
    result_file = tmp_path / "evidencepatch_result.json"
    result_file.write_text(json.dumps(_valid_result()))

    assert load_solver_result(result_file).action == "PATCH"


def test_missing_result_file_is_rejected(tmp_path):
    with pytest.raises(FileNotFoundError, match="does not exist"):
        load_solver_result(tmp_path / "missing.json")


def test_result_directory_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="not a regular file"):
        load_solver_result(tmp_path)


def test_symlink_result_file_is_rejected(tmp_path):
    target = tmp_path / "target.json"
    target.write_text(json.dumps(_valid_result()))
    symlink = tmp_path / "evidencepatch_result.json"
    symlink.symlink_to(target)

    with pytest.raises(ValueError, match="symbolic link"):
        load_solver_result(symlink)


def test_malformed_json_is_rejected(tmp_path):
    result_file = tmp_path / "evidencepatch_result.json"
    result_file.write_text("{not valid JSON")

    with pytest.raises(ValueError, match="invalid JSON"):
        load_solver_result(result_file)


def test_invalid_utf8_is_rejected(tmp_path):
    result_file = tmp_path / "evidencepatch_result.json"
    result_file.write_bytes(b"\xff\xfe")

    with pytest.raises(ValueError, match="not valid UTF-8"):
        load_solver_result(result_file)


def test_non_object_json_is_rejected(tmp_path):
    result_file = tmp_path / "evidencepatch_result.json"
    result_file.write_text("[]")

    with pytest.raises(ValueError, match="JSON object"):
        load_solver_result(result_file)


@pytest.mark.parametrize("invalid_value", [1, 0, "true", None])
def test_human_review_required_rejects_non_boolean(invalid_value):
    data = _valid_result()
    data["human_review_required"] = invalid_value

    with pytest.raises(ValueError, match="human_review_required.*boolean"):
        validate_solver_result(data)
