"""Machine-readable result contract shared by EvidencePatch solvers."""

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath


RESULT_FILENAME = "evidencepatch_result.json"
RESULT_SCHEMA_VERSION = 1
ALLOWED_ACTIONS = {"PATCH", "NO_PATCH", "ESCALATE"}

_REQUIRED_FIELDS = {
    "schema_version",
    "action",
    "changed_files",
    "evidence_ids",
    "human_review_required",
    "summary",
}


@dataclass(frozen=True)
class SolverResult:
    """Validated solver claims produced for one benchmark run."""

    schema_version: int
    action: str
    changed_files: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    human_review_required: bool
    summary: str


def _validate_string_list(value: object, field: str, *, nonempty: bool) -> list[str]:
    """Validate a JSON list of unique, non-empty strings."""
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a JSON list")
    if nonempty and not value:
        raise ValueError(f"{field} must be non-empty")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} must contain only non-empty strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{field} must not contain duplicate values")
    return value


def _validate_changed_path(raw_path: str) -> None:
    """Validate one normalized POSIX path relative to the repo root."""
    path = PurePosixPath(raw_path)
    components = raw_path.split("/")
    if path.is_absolute():
        raise ValueError(f"changed_files path must be relative: {raw_path!r}")
    if "\\" in raw_path:
        raise ValueError(f"changed_files path must use POSIX separators: {raw_path!r}")
    if "." in components or ".." in components:
        raise ValueError(f"changed_files path contains an unsafe component: {raw_path!r}")
    if not path.parts or path.as_posix() != raw_path:
        raise ValueError(f"changed_files path must be normalized: {raw_path!r}")
    if path.parts[0] == "repo":
        raise ValueError(f"changed_files path must be relative to repo, without repo/: {raw_path!r}")


def validate_solver_result(data: object) -> SolverResult:
    """Validate decoded JSON data and return an immutable solver result."""
    if not isinstance(data, dict):
        raise ValueError("Solver result must be a JSON object")

    fields = set(data)
    missing = _REQUIRED_FIELDS - fields
    extra = fields - _REQUIRED_FIELDS
    if missing:
        raise ValueError(f"Solver result is missing required fields: {sorted(missing)}")
    if extra:
        raise ValueError(f"Solver result contains unknown fields: {sorted(extra)}")

    schema_version = data["schema_version"]
    if isinstance(schema_version, bool) or schema_version != RESULT_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be integer {RESULT_SCHEMA_VERSION}")
    if not isinstance(schema_version, int):
        raise ValueError(f"schema_version must be integer {RESULT_SCHEMA_VERSION}")

    action = data["action"]
    if not isinstance(action, str) or action not in ALLOWED_ACTIONS:
        raise ValueError(f"action must be one of {sorted(ALLOWED_ACTIONS)}")

    changed_files = _validate_string_list(
        data["changed_files"], "changed_files", nonempty=False
    )
    for changed_path in changed_files:
        _validate_changed_path(changed_path)
    if action == "PATCH" and not changed_files:
        raise ValueError("changed_files must be non-empty when action is PATCH")
    if action in {"NO_PATCH", "ESCALATE"} and changed_files:
        raise ValueError(f"changed_files must be empty when action is {action}")

    evidence_ids = _validate_string_list(
        data["evidence_ids"], "evidence_ids", nonempty=True
    )

    human_review_required = data["human_review_required"]
    if not isinstance(human_review_required, bool):
        raise ValueError("human_review_required must be a boolean")

    summary = data["summary"]
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("summary must be a non-empty string")

    return SolverResult(
        schema_version=schema_version,
        action=action,
        changed_files=tuple(changed_files),
        evidence_ids=tuple(evidence_ids),
        human_review_required=human_review_required,
        summary=summary,
    )


def load_solver_result(path: Path) -> SolverResult:
    """Load and validate a solver result from a regular UTF-8 JSON file."""
    if path.is_symlink():
        raise ValueError(f"Solver result file must not be a symbolic link: {path}")
    if not path.exists():
        raise FileNotFoundError(f"Solver result file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Solver result path is not a regular file: {path}")

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"Solver result file is not valid UTF-8: {path}") from error
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Solver result file contains invalid JSON: {path}") from error
    return validate_solver_result(data)
