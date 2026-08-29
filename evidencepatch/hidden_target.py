"""Target-repository resolution for hidden benchmark evaluators."""

import os
from pathlib import Path


TARGET_REPO_ENV = "EVIDENCEPATCH_TARGET_REPO"


def resolve_hidden_target_repo(hidden_test_file: str | Path) -> Path:
    """Resolve the production repository a hidden test should evaluate."""
    canonical_repo = Path(hidden_test_file).resolve().parents[1] / "repo"
    override = os.environ.get(TARGET_REPO_ENV)
    if override is None:
        target = canonical_repo
    elif not override.strip():
        raise ValueError(f"{TARGET_REPO_ENV} must not be empty")
    else:
        target = Path(override)

    resolved_target = target.resolve()
    if not resolved_target.exists():
        raise FileNotFoundError(
            f"Hidden evaluator target repository does not exist: {resolved_target}"
        )
    if not resolved_target.is_dir():
        raise ValueError(
            f"Hidden evaluator target repository is not a directory: {resolved_target}"
        )
    return resolved_target
