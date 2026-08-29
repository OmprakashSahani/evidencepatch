"""Deterministic filesystem diffing for solver repository evaluation."""

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath


_IGNORED_DIRECTORIES = {"__pycache__", ".pytest_cache"}
_IGNORED_FILENAMES = {".coverage"}


@dataclass(frozen=True)
class RepositoryDiff:
    """File-level changes between a canonical and candidate repository."""

    added_files: tuple[str, ...]
    modified_files: tuple[str, ...]
    deleted_files: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in ("added_files", "modified_files", "deleted_files"):
            values = getattr(self, field)
            if not isinstance(values, tuple):
                raise ValueError(f"RepositoryDiff {field} must be a tuple")
            for value in values:
                if not isinstance(value, str):
                    raise ValueError(f"RepositoryDiff {field} paths must be strings")
                path = PurePosixPath(value)
                if (
                    not path.parts
                    or path.is_absolute()
                    or "\\" in value
                    or "." in value.split("/")
                    or ".." in value.split("/")
                    or path.as_posix() != value
                ):
                    raise ValueError(
                        f"RepositoryDiff {field} contains an invalid relative path: {value!r}"
                    )
            if len(set(values)) != len(values):
                raise ValueError(f"RepositoryDiff {field} paths must be unique")
            object.__setattr__(self, field, tuple(sorted(values)))

    @property
    def changed_files(self) -> tuple[str, ...]:
        """Return the sorted union of every changed file path."""
        return tuple(
            sorted(set(self.added_files + self.modified_files + self.deleted_files))
        )

    @property
    def is_clean(self) -> bool:
        """Return whether the repositories have no file-level differences."""
        return not (self.added_files or self.modified_files or self.deleted_files)


def _validate_root(root: Path, label: str) -> None:
    """Require a real, non-symlink repository directory."""
    if root.is_symlink():
        raise ValueError(f"{label} repository root must not be a symlink: {root}")
    if not root.exists():
        raise FileNotFoundError(f"{label} repository root does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"{label} repository root is not a directory: {root}")


def _is_ignored_file(name: str) -> bool:
    """Return whether a filename is an explicit runtime artifact."""
    return name in _IGNORED_FILENAMES or name.endswith(".pyc")


def _reject_symlinks(root: Path) -> None:
    """Reject symlinks anywhere in a repository, including ignored trees."""
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in directories + files:
            path = current_path / name
            if path.is_symlink():
                raise ValueError(f"Repository trees must not contain symlinks: {path}")


def _file_inventory(root: Path) -> dict[str, Path]:
    """Build a safe relative-path inventory of regular repository files."""
    inventory: dict[str, Path] = {}
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)

        for name in directories:
            path = current_path / name
            if path.is_symlink():
                raise ValueError(f"Repository trees must not contain symlinks: {path}")
        directories[:] = [
            name for name in directories if name not in _IGNORED_DIRECTORIES
        ]

        for name in files:
            path = current_path / name
            if path.is_symlink():
                raise ValueError(f"Repository trees must not contain symlinks: {path}")
            if _is_ignored_file(name) or not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            inventory[relative] = path
    return inventory


def compare_repositories(
    canonical_repo: Path,
    candidate_repo: Path,
) -> RepositoryDiff:
    """Compare two repository trees by regular-file paths and byte content."""
    _validate_root(canonical_repo, "Canonical")
    _validate_root(candidate_repo, "Candidate")
    _reject_symlinks(canonical_repo)
    _reject_symlinks(candidate_repo)

    canonical = _file_inventory(canonical_repo)
    candidate = _file_inventory(candidate_repo)
    canonical_paths = set(canonical)
    candidate_paths = set(candidate)

    added = tuple(sorted(candidate_paths - canonical_paths))
    deleted = tuple(sorted(canonical_paths - candidate_paths))
    modified = tuple(
        path
        for path in sorted(canonical_paths & candidate_paths)
        if canonical[path].read_bytes() != candidate[path].read_bytes()
    )
    return RepositoryDiff(
        added_files=added,
        modified_files=modified,
        deleted_files=deleted,
    )
