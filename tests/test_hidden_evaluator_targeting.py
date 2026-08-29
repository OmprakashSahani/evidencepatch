import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.hidden_target import TARGET_REPO_ENV
from evidencepatch.workspace import prepare_case_workspace


def test_case_01_hidden_evaluator_targets_staged_repository(tmp_path):
    case = PROJECT_ROOT / "benchmark" / "cases" / "case_01"
    canonical_rule = case / "repo" / "medication_rules" / "velunex.py"
    canonical_contents = canonical_rule.read_text()
    workspace = prepare_case_workspace(case, tmp_path / "solver_workspace")
    assert (workspace / "task.md").is_file()
    assert (workspace / "evidence" / "guideline_v2.md").is_file()
    assert (workspace / "repo" / "medication_rules" / "velunex.py").is_file()
    assert not (workspace / "hidden").exists()
    assert not list(workspace.rglob("ground_truth.json"))

    staged_rule = workspace / "repo" / "medication_rules" / "velunex.py"
    staged_rule.write_text(
        "def is_velunex_allowed(patient: dict) -> bool:\n"
        "    if patient.get(\"velunex_allergy\", False):\n"
        "        return False\n"
        "    if patient.get(\"marker_q\", 0) >= 70:\n"
        "        return False\n"
        "    return True\n"
    )

    environment = os.environ.copy()
    environment[TARGET_REPO_ENV] = str(workspace / "repo")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "benchmark/cases/case_01/hidden/test_case_01.py",
            "-q",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 passed" in result.stdout
    assert canonical_rule.read_text() == canonical_contents
