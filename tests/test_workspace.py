from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.workspace import prepare_case_workspace


CASE_01 = PROJECT_ROOT / "benchmark" / "cases" / "case_01"


def test_case_workspace_contains_only_public_case_inputs(tmp_path):
    destination = tmp_path / "solver_workspace"

    workspace = prepare_case_workspace(CASE_01, destination)

    assert workspace == destination
    assert (workspace / "task.md").is_file()
    assert (workspace / "evidence" / "guideline_v2.md").is_file()
    assert (workspace / "repo" / "medication_rules" / "velunex.py").is_file()
    assert (workspace / "repo" / "tests" / "test_velunex.py").is_file()
    assert not (workspace / "hidden").exists()
    assert not list(workspace.rglob("ground_truth.json"))
    assert not list(workspace.rglob("test_case_01.py"))


def test_copied_workspace_is_independent_from_source(tmp_path):
    source = CASE_01 / "repo" / "medication_rules" / "velunex.py"
    original_contents = source.read_text()
    workspace = prepare_case_workspace(CASE_01, tmp_path / "solver_workspace")
    copied = workspace / "repo" / "medication_rules" / "velunex.py"

    copied.write_text("# changed only in the solver workspace\n")

    assert source.read_text() == original_contents
    assert copied.read_text() != original_contents


def test_missing_required_public_input_is_rejected(tmp_path):
    malformed_case = tmp_path / "malformed_case"
    malformed_case.mkdir()
    (malformed_case / "task.md").write_text("Synthetic task\n")
    (malformed_case / "repo").mkdir()

    with pytest.raises(FileNotFoundError, match="evidence"):
        prepare_case_workspace(malformed_case, tmp_path / "solver_workspace")


def test_nonempty_destination_is_rejected(tmp_path):
    destination = tmp_path / "solver_workspace"
    destination.mkdir()
    existing = destination / "existing.txt"
    existing.write_text("keep me\n")

    with pytest.raises(ValueError, match="not empty"):
        prepare_case_workspace(CASE_01, destination)

    assert existing.read_text() == "keep me\n"
