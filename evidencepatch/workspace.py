"""Utilities for preparing isolated benchmark solver workspaces."""

from pathlib import Path
import shutil


def prepare_case_workspace(case_dir: Path, destination: Path) -> Path:
    """Copy a case's public inputs into a new solver workspace."""
    if not case_dir.exists():
        raise FileNotFoundError(f"Case directory does not exist: {case_dir}")
    if not case_dir.is_dir():
        raise ValueError(f"Case path is not a directory: {case_dir}")

    task = case_dir / "task.md"
    evidence = case_dir / "evidence"
    repository = case_dir / "repo"
    if not task.is_file():
        raise FileNotFoundError(f"Required case file is missing: {task}")
    for required_dir in (evidence, repository):
        if not required_dir.is_dir():
            raise FileNotFoundError(
                f"Required case directory is missing: {required_dir}"
            )

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
