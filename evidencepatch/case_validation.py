"""Validation for canonical EvidencePatch benchmark cases."""

import json
import os
from pathlib import Path, PurePosixPath


REQUIRED_GROUND_TRUTH_FIELDS = {
    "case_id",
    "expected_action",
    "expected_impacted_production_files",
    "required_evidence_ids",
    "requires_human_review",
    "evaluation_basis",
    "required_behaviors",
    "preserve_unrelated_behavior",
}
PRIVATE_TASK_TERMS = ("ground_truth.json", "hidden evaluator", "hidden tests")


def _require_path(path: Path, kind: str) -> None:
    """Require a non-symlink path of the requested kind."""
    if path.is_symlink():
        raise ValueError(f"Required case path must not be a symlink: {path}")
    valid = path.is_file() if kind == "file" else path.is_dir()
    if not valid:
        raise ValueError(f"Required case {kind} is missing or invalid: {path}")


def _regular_files_without_symlinks(root: Path) -> list[Path]:
    """Return regular files below root without following symbolic links."""
    files_found: list[Path] = []
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in directories + files:
            path = current_path / name
            if path.is_symlink():
                raise ValueError(f"Symlinks are not allowed under {root}: {path}")
        files_found.extend(
            path for name in files if (path := current_path / name).is_file()
        )
    return files_found


def _require_unique_strings(value: object, field: str, *, nonempty: bool) -> list[str]:
    """Validate a JSON list containing unique strings."""
    if not isinstance(value, list) or (nonempty and not value):
        qualifier = "non-empty " if nonempty else ""
        raise ValueError(f"{field} must be a {qualifier}JSON list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} must contain only non-empty strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{field} must contain unique strings")
    return value


def _validate_impacted_files(data: dict, repository: Path) -> None:
    """Validate impacted production paths against the case repository."""
    impacted = _require_unique_strings(
        data["expected_impacted_production_files"],
        "expected_impacted_production_files",
        nonempty=data["expected_action"] == "PATCH",
    )
    for raw_path in impacted:
        path = PurePosixPath(raw_path)
        if path.is_absolute():
            raise ValueError(f"Impacted production path must be relative: {raw_path}")
        if "\\" in raw_path or path.as_posix() != raw_path:
            raise ValueError(
                f"Impacted production path must use normalized POSIX style: {raw_path}"
            )
        if ".." in path.parts:
            raise ValueError(f"Impacted production path contains traversal: {raw_path}")
        if path.parts and path.parts[0] == "tests":
            raise ValueError(f"Impacted file must not be under repo/tests: {raw_path}")
        target = repository.joinpath(*path.parts)
        if not target.is_file():
            raise ValueError(f"Impacted production file does not exist: {raw_path}")


def validate_case(case_dir: Path) -> None:
    """Validate a benchmark case's structure and canonical ground truth."""
    if case_dir.is_symlink() or not case_dir.is_dir():
        raise ValueError(f"Case directory is missing, invalid, or a symlink: {case_dir}")

    task = case_dir / "task.md"
    evidence = case_dir / "evidence"
    repository = case_dir / "repo"
    hidden = case_dir / "hidden"
    ground_truth = hidden / "ground_truth.json"
    _require_path(task, "file")
    _require_path(evidence, "directory")
    _require_path(repository, "directory")
    _require_path(hidden, "directory")
    _require_path(ground_truth, "file")

    evidence_files = _regular_files_without_symlinks(evidence)
    repository_files = _regular_files_without_symlinks(repository)
    if not evidence_files:
        raise ValueError("evidence/ must contain at least one regular file")
    production_python = [
        path
        for path in repository_files
        if path.suffix == ".py" and path.relative_to(repository).parts[0] != "tests"
    ]
    if not production_python:
        raise ValueError("repo/ must contain a production Python file outside tests/")

    try:
        task_text = task.read_text(encoding="utf-8")
    except UnicodeError as error:
        raise ValueError("task.md must contain valid UTF-8 text") from error
    if not task_text.strip():
        raise ValueError("task.md must not be empty")
    lowered_task = task_text.casefold()
    for term in PRIVATE_TASK_TERMS:
        if term in lowered_task:
            raise ValueError(f"task.md leaks benchmark-private term: {term}")

    try:
        data = json.loads(ground_truth.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("ground_truth.json must contain valid UTF-8 JSON") from error
    if not isinstance(data, dict):
        raise ValueError("ground_truth.json must contain a JSON object")
    missing = REQUIRED_GROUND_TRUTH_FIELDS - data.keys()
    if missing:
        raise ValueError(f"ground_truth.json is missing required fields: {sorted(missing)}")

    case_id = data["case_id"]
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a non-empty string")
    if case_id != case_dir.name:
        raise ValueError(
            f"case_id must match case directory name {case_dir.name!r}: {case_id!r}"
        )

    action = data["expected_action"]
    if not isinstance(action, str) or action not in {"PATCH", "NO_PATCH", "ESCALATE"}:
        raise ValueError("expected_action must be PATCH, NO_PATCH, or ESCALATE")
    _validate_impacted_files(data, repository)

    evidence_ids = _require_unique_strings(
        data["required_evidence_ids"], "required_evidence_ids", nonempty=True
    )
    for field in ("requires_human_review", "preserve_unrelated_behavior"):
        if not isinstance(data[field], bool):
            raise ValueError(f"{field} must be a boolean")
    if data["evaluation_basis"] != "behavior":
        raise ValueError("evaluation_basis must be the non-empty string 'behavior'")

    behaviors = data["required_behaviors"]
    if not isinstance(behaviors, list) or not behaviors:
        raise ValueError("required_behaviors must be a non-empty JSON list")
    for index, behavior in enumerate(behaviors):
        if not isinstance(behavior, dict):
            raise ValueError(f"required_behaviors[{index}] must be a JSON object")
        if "expected_allowed" not in behavior:
            raise ValueError(
                f"required_behaviors[{index}] must contain expected_allowed"
            )
        if not isinstance(behavior["expected_allowed"], bool):
            raise ValueError(
                f"required_behaviors[{index}].expected_allowed must be a boolean"
            )

    evidence_texts: list[str] = []
    for path in evidence_files:
        try:
            evidence_texts.append(path.read_text(encoding="utf-8"))
        except UnicodeError as error:
            raise ValueError(f"Evidence file must contain valid UTF-8 text: {path}") from error
    for evidence_id in evidence_ids:
        if not any(evidence_id in text for text in evidence_texts):
            raise ValueError(f"Required evidence ID not found in evidence/: {evidence_id}")
