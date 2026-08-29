from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.hidden_target import (
    TARGET_REPO_ENV,
    resolve_hidden_target_repo,
)


def test_default_target_is_canonical_case_repository(tmp_path, monkeypatch):
    hidden_test = tmp_path / "case_01" / "hidden" / "test_case_01.py"
    canonical_repo = tmp_path / "case_01" / "repo"
    canonical_repo.mkdir(parents=True)
    monkeypatch.delenv(TARGET_REPO_ENV, raising=False)

    assert resolve_hidden_target_repo(hidden_test) == canonical_repo.resolve()


def test_environment_override_selects_target_repository(tmp_path, monkeypatch):
    target_repo = tmp_path / "staged_repo"
    target_repo.mkdir()
    monkeypatch.setenv(TARGET_REPO_ENV, str(target_repo))

    resolved = resolve_hidden_target_repo(
        tmp_path / "case_01" / "hidden" / "test_case_01.py"
    )

    assert resolved == target_repo.resolve()


def test_missing_override_target_is_rejected(tmp_path, monkeypatch):
    missing = tmp_path / "missing_repo"
    monkeypatch.setenv(TARGET_REPO_ENV, str(missing))

    with pytest.raises(FileNotFoundError, match="does not exist"):
        resolve_hidden_target_repo(
            tmp_path / "case_01" / "hidden" / "test_case_01.py"
        )


def test_override_target_file_is_rejected(tmp_path, monkeypatch):
    target_file = tmp_path / "not_a_repo"
    target_file.write_text("not a directory\n")
    monkeypatch.setenv(TARGET_REPO_ENV, str(target_file))

    with pytest.raises(ValueError, match="not a directory"):
        resolve_hidden_target_repo(
            tmp_path / "case_01" / "hidden" / "test_case_01.py"
        )
