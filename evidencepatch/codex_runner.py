"""Low-level reproducible invocation wrapper for non-interactive Codex."""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import subprocess
import time


@dataclass(frozen=True)
class CodexRunResult:
    """Process and artifact metadata from one Codex invocation."""

    model: str
    codex_version: str
    returncode: int | None
    timed_out: bool
    duration_seconds: float
    events_path: Path
    stderr_path: Path
    prompt_path: Path
    metadata_path: Path

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("CodexRunResult model must be a non-empty string")
        if not isinstance(self.codex_version, str) or not self.codex_version.strip():
            raise ValueError("CodexRunResult codex_version must be a non-empty string")
        if (
            self.returncode is not None
            and (isinstance(self.returncode, bool) or not isinstance(self.returncode, int))
        ):
            raise ValueError("CodexRunResult returncode must be an integer or None")
        if not isinstance(self.timed_out, bool):
            raise ValueError("CodexRunResult timed_out must be a boolean")
        if (
            isinstance(self.duration_seconds, bool)
            or not isinstance(self.duration_seconds, (int, float))
            or not math.isfinite(self.duration_seconds)
            or self.duration_seconds < 0
        ):
            raise ValueError(
                "CodexRunResult duration_seconds must be a finite non-negative number"
            )
        for field in ("events_path", "stderr_path", "prompt_path", "metadata_path"):
            if not isinstance(getattr(self, field), Path):
                raise ValueError(f"CodexRunResult {field} must be a Path")

    @property
    def completed_successfully(self) -> bool:
        """Return whether Codex exited successfully without timing out."""
        return not self.timed_out and self.returncode == 0


def _require_nonempty_string(value: object, name: str) -> str:
    """Require a non-empty string without coercion."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def build_codex_exec_command(workspace: Path, model: str) -> tuple[str, ...]:
    """Build the exact plain-baseline Codex command."""
    _require_nonempty_string(model, "model")
    return (
        "codex",
        "--ask-for-approval",
        "never",
        "exec",
        "--model",
        model,
        "--sandbox",
        "workspace-write",
        "--cd",
        str(workspace),
        "--skip-git-repo-check",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--json",
        "--color",
        "never",
        "-",
    )


def _is_within(path: Path, parent: Path) -> bool:
    """Return whether path equals or is below parent."""
    return path == parent or parent in path.parents


def _validate_workspace(workspace: Path) -> Path:
    """Validate and resolve the solver workspace."""
    if workspace.is_symlink():
        raise ValueError(f"Workspace must not be a symlink: {workspace}")
    if not workspace.exists():
        raise FileNotFoundError(f"Workspace does not exist: {workspace}")
    if not workspace.is_dir():
        raise ValueError(f"Workspace is not a directory: {workspace}")
    return workspace.resolve()


def _prepare_artifacts_dir(artifacts_dir: Path, workspace: Path) -> Path:
    """Validate separation and create an empty artifact directory."""
    if artifacts_dir.is_symlink():
        raise ValueError(f"Artifacts directory must not be a symlink: {artifacts_dir}")
    resolved = artifacts_dir.resolve()
    if _is_within(resolved, workspace):
        raise ValueError("Artifacts directory must not be inside solver workspace")
    if _is_within(workspace, resolved):
        raise ValueError("Solver workspace must not be inside artifacts directory")
    if artifacts_dir.exists():
        if not artifacts_dir.is_dir():
            raise ValueError(f"Artifacts path is not a directory: {artifacts_dir}")
        if any(artifacts_dir.iterdir()):
            raise ValueError(f"Artifacts directory is not empty: {artifacts_dir}")
    else:
        artifacts_dir.mkdir(parents=True)
    return artifacts_dir.resolve()


def _codex_version() -> str:
    """Return the installed Codex version or raise an environment error."""
    try:
        completed = subprocess.run(
            ["codex", "--version"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"Unable to execute 'codex --version': {error}") from error
    version = completed.stdout.strip()
    if completed.returncode != 0 or not version:
        raise RuntimeError(
            "Unable to determine Codex version: version command failed or returned no output"
        )
    return version


def _captured_text(value: str | bytes | None) -> str:
    """Normalize captured subprocess output, including timeout payloads."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_codex(
    workspace: Path,
    artifacts_dir: Path,
    prompt: str,
    *,
    model: str = "gpt-5.6-sol",
    timeout_seconds: float = 180.0,
) -> CodexRunResult:
    """Run Codex once and persist raw, runner-owned execution artifacts."""
    _require_nonempty_string(prompt, "prompt")
    _require_nonempty_string(model, "model")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise ValueError("timeout_seconds must be a positive finite number")

    resolved_workspace = _validate_workspace(workspace)
    resolved_artifacts = _prepare_artifacts_dir(artifacts_dir, resolved_workspace)
    codex_version = _codex_version()
    command = build_codex_exec_command(resolved_workspace, model)

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        duration = time.monotonic() - started
        returncode = completed.returncode
        timed_out = False
        stdout = _captured_text(completed.stdout)
        stderr = _captured_text(completed.stderr)
    except subprocess.TimeoutExpired as error:
        duration = time.monotonic() - started
        returncode = None
        timed_out = True
        stdout = _captured_text(error.stdout)
        stderr = _captured_text(error.stderr)

    prompt_path = resolved_artifacts / "prompt.txt"
    events_path = resolved_artifacts / "events.jsonl"
    stderr_path = resolved_artifacts / "stderr.txt"
    metadata_path = resolved_artifacts / "run_metadata.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    events_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    metadata = {
        "schema_version": 1,
        "model": model,
        "codex_version": codex_version,
        "sandbox": "workspace-write",
        "approval_policy": "never",
        "search_enabled": False,
        "ephemeral": True,
        "ignore_user_config": True,
        "ignore_rules": True,
        "returncode": returncode,
        "timed_out": timed_out,
        "duration_seconds": duration,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return CodexRunResult(
        model=model,
        codex_version=codex_version,
        returncode=returncode,
        timed_out=timed_out,
        duration_seconds=duration,
        events_path=events_path,
        stderr_path=stderr_path,
        prompt_path=prompt_path,
        metadata_path=metadata_path,
    )
