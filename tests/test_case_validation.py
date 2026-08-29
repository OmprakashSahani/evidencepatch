import json
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.case_validation import validate_case


CASES = PROJECT_ROOT / "benchmark" / "cases"


def _make_valid_case(tmp_path: Path, name: str = "temporary_case") -> Path:
    case = tmp_path / name
    (case / "evidence").mkdir(parents=True)
    (case / "repo" / "medication_rules").mkdir(parents=True)
    (case / "repo" / "tests").mkdir()
    (case / "hidden").mkdir()
    (case / "task.md").write_text("Update the synthetic medication rule.\n")
    (case / "evidence" / "guideline.md").write_text("Evidence ID: SYN-TEMP-1\n")
    (case / "repo" / "medication_rules" / "rule.py").write_text(
        "def is_allowed(patient):\n    return True\n"
    )
    ground_truth = {
        "case_id": name,
        "expected_action": "PATCH",
        "expected_impacted_production_files": ["medication_rules/rule.py"],
        "required_evidence_ids": ["SYN-TEMP-1"],
        "requires_human_review": True,
        "evaluation_basis": "behavior",
        "required_behaviors": [{"input_value": 1, "expected_allowed": True}],
        "preserve_unrelated_behavior": True,
    }
    (case / "hidden" / "ground_truth.json").write_text(json.dumps(ground_truth))
    return case


def _ground_truth(case: Path) -> dict:
    return json.loads((case / "hidden" / "ground_truth.json").read_text())


def _write_ground_truth(case: Path, data: dict) -> None:
    (case / "hidden" / "ground_truth.json").write_text(json.dumps(data))


def test_case_01_is_valid():
    assert validate_case(CASES / "case_01") is None


def test_case_02_is_valid():
    assert validate_case(CASES / "case_02") is None


def test_case_id_must_match_directory_name(tmp_path):
    case = _make_valid_case(tmp_path)
    data = _ground_truth(case)
    data["case_id"] = "different_case"
    _write_ground_truth(case, data)

    with pytest.raises(ValueError, match="case_id must match"):
        validate_case(case)


@pytest.mark.parametrize("unsafe_path", ["/absolute/rule.py", "../rule.py"])
def test_impacted_production_path_must_be_safe(tmp_path, unsafe_path):
    case = _make_valid_case(tmp_path)
    data = _ground_truth(case)
    data["expected_impacted_production_files"] = [unsafe_path]
    _write_ground_truth(case, data)

    with pytest.raises(ValueError, match="relative|traversal"):
        validate_case(case)


def test_required_evidence_id_must_appear_in_evidence(tmp_path):
    case = _make_valid_case(tmp_path)
    data = _ground_truth(case)
    data["required_evidence_ids"] = ["SYN-ABSENT"]
    _write_ground_truth(case, data)

    with pytest.raises(ValueError, match="evidence ID not found"):
        validate_case(case)


def test_evidence_symlink_is_rejected(tmp_path):
    case = _make_valid_case(tmp_path)
    private = case / "private.txt"
    private.write_text("private benchmark content\n")
    (case / "evidence" / "linked.txt").symlink_to(private)

    with pytest.raises(ValueError, match="Symlinks"):
        validate_case(case)


def test_task_must_not_leak_ground_truth_filename(tmp_path):
    case = _make_valid_case(tmp_path)
    (case / "task.md").write_text("Read GROUND_TRUTH.JSON for the answer.\n")

    with pytest.raises(ValueError, match="benchmark-private"):
        validate_case(case)
