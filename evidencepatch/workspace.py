"""Utilities for preparing isolated benchmark solver workspaces."""

import os
from pathlib import Path
import shutil


def _reject_symlinks(root: Path) -> None:
    """Reject a public input tree containing any symbolic link."""
    if root.is_symlink():
        raise ValueError(f"Symbolic links are not allowed in case inputs: {root}")

    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in directories + files:
            path = current_path / name
            if path.is_symlink():
                raise ValueError(
                    f"Symbolic links are not allowed in case inputs: {path}"
                )


def prepare_case_workspace(case_dir: Path, destination: Path) -> Path:
    """Copy a case's public inputs into a new solver workspace."""
    if not case_dir.exists():
        raise FileNotFoundError(f"Case directory does not exist: {case_dir}")
    if not case_dir.is_dir():
        raise ValueError(f"Case path is not a directory: {case_dir}")

    task = case_dir / "task.md"
    evidence = case_dir / "evidence"
    repository = case_dir / "repo"
    if task.is_symlink():
        raise ValueError(f"Symbolic links are not allowed in case inputs: {task}")
    if not task.is_file():
        raise FileNotFoundError(f"Required case file is missing: {task}")
    for required_dir in (evidence, repository):
        if required_dir.is_symlink():
            raise ValueError(
                f"Symbolic links are not allowed in case inputs: {required_dir}"
            )
        if not required_dir.is_dir():
            raise FileNotFoundError(
                f"Required case directory is missing: {required_dir}"
            )
        _reject_symlinks(required_dir)

    if destination.exists():
        if not destination.is_dir():
            raise ValueError(f"Destination is not a directory: {destination}")
        if any(destination.iterdir()):
            raise ValueError(f"Destination is not empty: {destination}")
    else:
        destination.mkdir(parents=True)

    shutil.copy2(task, destination / "task.md")
    shutil.copytree(evidence, destination / "evidence")
    shutil.copytree(repository, destination / "repo")
    return destination
