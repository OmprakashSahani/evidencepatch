from dataclasses import FrozenInstanceError
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.codex_runner import (
    CodexRunResult,
    build_codex_exec_command,
    run_codex,
)


def _fake_runs(monkeypatch, *, returncode=0, stdout='{"event":"done"}\n', stderr=""):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command == ["codex", "--version"]:
            return SimpleNamespace(returncode=0, stdout="codex-cli 1.2.3\n", stderr="")
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def _run(tmp_path, monkeypatch, **kwargs):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = tmp_path / "artifacts"
    calls = _fake_runs(monkeypatch, **kwargs)
    result = run_codex(workspace, artifacts, "Prompt text")
    return result, calls, workspace, artifacts


def test_exact_command_construction(tmp_path):
    workspace = tmp_path / "workspace"
    expected = (
        "codex",
        "--ask-for-approval",
        "never",
        "exec",
        "--model",
        "gpt-5.6-sol",
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

    command = build_codex_exec_command(workspace, "gpt-5.6-sol")

    assert command == expected
    assert command[-1] == "-"
    for forbidden in (
        "--search",
        "--add-dir",
        "--approve-for-me",
        "--dangerously-bypass-approvals-and-sandbox",
        "danger-full-access",
    ):
        assert forbidden not in command


def test_prompt_is_passed_only_through_stdin(tmp_path, monkeypatch):
    result, calls, _, _ = _run(tmp_path, monkeypatch)
    command, kwargs = calls[1]

    assert result.completed_successfully is True
    assert kwargs["input"] == "Prompt text"
    assert "Prompt text" not in command
    assert kwargs["check"] is False
    assert "shell" not in kwargs


def test_successful_run_writes_exact_artifacts(tmp_path, monkeypatch):
    result, _, _, artifacts = _run(
        tmp_path,
        monkeypatch,
        stdout='{"event":"done"}\n',
        stderr="sample stderr\n",
    )

    assert result.completed_successfully is True
    assert result.timed_out is False
    assert result.returncode == 0
    assert result.codex_version == "codex-cli 1.2.3"
    assert (artifacts / "prompt.txt").read_text() == "Prompt text"
    assert (artifacts / "events.jsonl").read_text() == '{"event":"done"}\n'
    assert (artifacts / "stderr.txt").read_text() == "sample stderr\n"
    metadata = json.loads((artifacts / "run_metadata.json").read_text())
    assert metadata["model"] == "gpt-5.6-sol"
    assert metadata["search_enabled"] is False
    assert metadata["returncode"] == 0
    assert metadata["timed_out"] is False


def test_nonzero_run_returns_normally_and_writes_artifacts(tmp_path, monkeypatch):
    result, _, _, artifacts = _run(
        tmp_path, monkeypatch, returncode=1, stdout="partial\n", stderr="failure\n"
    )

    assert result.completed_successfully is False
    assert result.returncode == 1
    assert result.timed_out is False
    assert (artifacts / "events.jsonl").read_text() == "partial\n"
    assert (artifacts / "stderr.txt").read_text() == "failure\n"


def test_timeout_returns_result_and_writes_partial_artifacts(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = tmp_path / "artifacts"

    def fake_run(command, **kwargs):
        if command == ["codex", "--version"]:
            return SimpleNamespace(returncode=0, stdout="codex-cli 1.2.3\n", stderr="")
        raise subprocess.TimeoutExpired(
            command, kwargs["timeout"], output="partial stdout", stderr="partial stderr"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_codex(workspace, artifacts, "Prompt text", timeout_seconds=1)

    assert result.completed_successfully is False
    assert result.timed_out is True
    assert result.returncode is None
    assert (artifacts / "events.jsonl").read_text() == "partial stdout"
    assert (artifacts / "stderr.txt").read_text() == "partial stderr"
    assert json.loads((artifacts / "run_metadata.json").read_text())["timed_out"] is True


@pytest.mark.parametrize("workspace_kind", ["missing", "file", "symlink"])
def test_invalid_workspace_is_rejected(tmp_path, monkeypatch, workspace_kind):
    workspace = tmp_path / "workspace"
    if workspace_kind == "file":
        workspace.write_text("file\n")
    elif workspace_kind == "symlink":
        target = tmp_path / "target"
        target.mkdir()
        workspace.symlink_to(target, target_is_directory=True)
    _fake_runs(monkeypatch)

    with pytest.raises((FileNotFoundError, ValueError), match="Workspace"):
        run_codex(workspace, tmp_path / "artifacts", "Prompt text")


@pytest.mark.parametrize("artifact_kind", ["file", "symlink", "nonempty"])
def test_invalid_artifacts_directory_is_rejected(tmp_path, monkeypatch, artifact_kind):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = tmp_path / "artifacts"
    if artifact_kind == "file":
        artifacts.write_text("file\n")
    elif artifact_kind == "symlink":
        target = tmp_path / "target"
        target.mkdir()
        artifacts.symlink_to(target, target_is_directory=True)
    else:
        artifacts.mkdir()
        (artifacts / "existing.txt").write_text("existing\n")
    _fake_runs(monkeypatch)

    with pytest.raises(ValueError, match="Artifacts"):
        run_codex(workspace, artifacts, "Prompt text")


def test_artifacts_inside_workspace_are_rejected(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _fake_runs(monkeypatch)

    with pytest.raises(ValueError, match="inside solver workspace"):
        run_codex(workspace, workspace / "artifacts", "Prompt text")


def test_workspace_inside_artifacts_is_rejected(tmp_path, monkeypatch):
    artifacts = tmp_path / "artifacts"
    workspace = artifacts / "workspace"
    workspace.mkdir(parents=True)
    _fake_runs(monkeypatch)

    with pytest.raises(ValueError, match="workspace must not be inside"):
        run_codex(workspace, artifacts, "Prompt text")


@pytest.mark.parametrize("invalid_prompt", ["", "   ", None, 1])
def test_invalid_prompt_is_rejected(tmp_path, invalid_prompt):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(ValueError, match="prompt.*non-empty"):
        run_codex(workspace, tmp_path / "artifacts", invalid_prompt)


@pytest.mark.parametrize("invalid_model", ["", "   ", None, 1])
def test_invalid_model_is_rejected(tmp_path, invalid_model):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(ValueError, match="model.*non-empty"):
        run_codex(workspace, tmp_path / "artifacts", "Prompt", model=invalid_model)


@pytest.mark.parametrize("invalid_timeout", [0, -1, True, math.inf, math.nan])
def test_invalid_timeout_is_rejected(tmp_path, invalid_timeout):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(ValueError, match="timeout_seconds"):
        run_codex(
            workspace,
            tmp_path / "artifacts",
            "Prompt",
            timeout_seconds=invalid_timeout,
        )


@pytest.mark.parametrize("failure_kind", ["nonzero", "empty", "missing"])
def test_codex_version_failure_raises_runtime_error(tmp_path, monkeypatch, failure_kind):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def fake_run(command, **kwargs):
        if failure_kind == "missing":
            raise FileNotFoundError("codex")
        if failure_kind == "nonzero":
            return SimpleNamespace(returncode=1, stdout="", stderr="failure")
        return SimpleNamespace(returncode=0, stdout="   ", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="Codex version|codex --version"):
        run_codex(workspace, tmp_path / "artifacts", "Prompt")


def _valid_run_result(**overrides):
    values = {
        "model": "gpt-5.6-sol",
        "codex_version": "codex-cli 1.2.3",
        "returncode": 0,
        "timed_out": False,
        "duration_seconds": 1.0,
        "events_path": Path("events.jsonl"),
        "stderr_path": Path("stderr.txt"),
        "prompt_path": Path("prompt.txt"),
        "metadata_path": Path("run_metadata.json"),
    }
    values.update(overrides)
    return CodexRunResult(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"model": ""},
        {"codex_version": " "},
        {"returncode": True},
        {"timed_out": 0},
        {"duration_seconds": -1},
        {"duration_seconds": math.inf},
        {"duration_seconds": math.nan},
    ],
)
def test_codex_run_result_rejects_invalid_values(overrides):
    with pytest.raises(ValueError):
        _valid_run_result(**overrides)


def test_codex_run_result_is_immutable():
    result = _valid_run_result()

    with pytest.raises(FrozenInstanceError):
        result.returncode = 1
