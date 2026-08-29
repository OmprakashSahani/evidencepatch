from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.repo_diff import RepositoryDiff, compare_repositories


def _repos(tmp_path):
    canonical = tmp_path / "canonical"
    candidate = tmp_path / "candidate"
    canonical.mkdir()
    candidate.mkdir()
    return canonical, candidate


def _write(root, relative, content=b"content"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_identical_repositories_are_clean(tmp_path):
    canonical, candidate = _repos(tmp_path)
    _write(canonical, "rules/example.py")
    _write(candidate, "rules/example.py")

    result = compare_repositories(canonical, candidate)

    assert result.is_clean is True
    assert result.added_files == ()
    assert result.modified_files == ()
    assert result.deleted_files == ()
    assert result.changed_files == ()


def test_modified_text_file_is_detected(tmp_path):
    canonical, candidate = _repos(tmp_path)
    _write(canonical, "rule.py", b"old\n")
    _write(candidate, "rule.py", b"new\n")

    assert compare_repositories(canonical, candidate).modified_files == ("rule.py",)


def test_modified_binary_file_is_detected_by_bytes(tmp_path):
    canonical, candidate = _repos(tmp_path)
    _write(canonical, "asset.bin", b"\x00\xff")
    _write(candidate, "asset.bin", b"\x00\xfe")

    assert compare_repositories(canonical, candidate).modified_files == ("asset.bin",)


def test_added_file_is_detected(tmp_path):
    canonical, candidate = _repos(tmp_path)
    _write(candidate, "new.py")

    assert compare_repositories(canonical, candidate).added_files == ("new.py",)


def test_deleted_file_is_detected(tmp_path):
    canonical, candidate = _repos(tmp_path)
    _write(canonical, "old.py")

    assert compare_repositories(canonical, candidate).deleted_files == ("old.py",)


def test_simultaneous_changes_are_sorted_deterministically(tmp_path):
    canonical, candidate = _repos(tmp_path)
    _write(canonical, "z_deleted.py")
    _write(canonical, "c_modified.py", b"old")
    _write(candidate, "c_modified.py", b"new")
    _write(candidate, "b_added.py")
    _write(candidate, "a_added.py")

    result = compare_repositories(canonical, candidate)

    assert result.added_files == ("a_added.py", "b_added.py")
    assert result.modified_files == ("c_modified.py",)
    assert result.deleted_files == ("z_deleted.py",)
    assert result.changed_files == (
        "a_added.py",
        "b_added.py",
        "c_modified.py",
        "z_deleted.py",
    )


def test_nested_paths_use_posix_separators(tmp_path):
    canonical, candidate = _repos(tmp_path)
    _write(candidate, "medication_rules/nested/rule.py")

    assert compare_repositories(canonical, candidate).added_files == (
        "medication_rules/nested/rule.py",
    )


@pytest.mark.parametrize("artifact_dir", ["__pycache__", ".pytest_cache"])
def test_runtime_artifact_directories_are_ignored(tmp_path, artifact_dir):
    canonical, candidate = _repos(tmp_path)
    _write(canonical, f"nested/{artifact_dir}/old")
    _write(candidate, f"nested/{artifact_dir}/new")

    assert compare_repositories(canonical, candidate).is_clean is True


@pytest.mark.parametrize("artifact_file", ["module.pyc", ".coverage"])
def test_runtime_artifact_files_are_ignored(tmp_path, artifact_file):
    canonical, candidate = _repos(tmp_path)
    _write(canonical, f"nested/{artifact_file}", b"old")
    _write(candidate, f"nested/{artifact_file}", b"new")

    assert compare_repositories(canonical, candidate).is_clean is True


def test_normal_dotfile_is_not_ignored(tmp_path):
    canonical, candidate = _repos(tmp_path)
    _write(candidate, ".config")

    assert compare_repositories(canonical, candidate).added_files == (".config",)


@pytest.mark.parametrize("missing_side", ["canonical", "candidate"])
def test_missing_root_is_rejected(tmp_path, missing_side):
    canonical, candidate = _repos(tmp_path)
    missing = tmp_path / missing_side / "missing"
    if missing_side == "canonical":
        canonical = missing
    else:
        candidate = missing

    with pytest.raises(FileNotFoundError, match=f"{missing_side.title()}.*does not exist"):
        compare_repositories(canonical, candidate)


@pytest.mark.parametrize("file_side", ["canonical", "candidate"])
def test_regular_file_root_is_rejected(tmp_path, file_side):
    canonical, candidate = _repos(tmp_path)
    root_file = tmp_path / f"{file_side}.txt"
    root_file.write_text("not a directory\n")
    if file_side == "canonical":
        canonical = root_file
    else:
        candidate = root_file

    with pytest.raises(ValueError, match="not a directory"):
        compare_repositories(canonical, candidate)


@pytest.mark.parametrize("symlink_side", ["canonical", "candidate"])
def test_symlink_root_is_rejected(tmp_path, symlink_side):
    canonical, candidate = _repos(tmp_path)
    target = tmp_path / f"{symlink_side}_target"
    target.mkdir()
    symlink = tmp_path / f"{symlink_side}_link"
    symlink.symlink_to(target, target_is_directory=True)
    if symlink_side == "canonical":
        canonical = symlink
    else:
        candidate = symlink

    with pytest.raises(ValueError, match="root must not be a symlink"):
        compare_repositories(canonical, candidate)


def test_nested_file_symlink_is_rejected(tmp_path):
    canonical, candidate = _repos(tmp_path)
    target = tmp_path / "private.txt"
    target.write_text("private\n")
    (candidate / "linked.txt").symlink_to(target)

    with pytest.raises(ValueError, match="symlinks"):
        compare_repositories(canonical, candidate)


def test_nested_directory_symlink_is_rejected(tmp_path):
    canonical, candidate = _repos(tmp_path)
    target = tmp_path / "private"
    target.mkdir()
    (candidate / "linked").symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="symlinks"):
        compare_repositories(canonical, candidate)


def test_empty_directory_only_difference_is_clean(tmp_path):
    canonical, candidate = _repos(tmp_path)
    (candidate / "empty" / "nested").mkdir(parents=True)

    assert compare_repositories(canonical, candidate).is_clean is True


def test_changed_files_is_sorted_union():
    result = RepositoryDiff(
        added_files=("z.py", "a.py"),
        modified_files=("m.py",),
        deleted_files=("a.py", "b.py"),
    )

    assert result.changed_files == ("a.py", "b.py", "m.py", "z.py")
    assert result.added_files == ("a.py", "z.py")
