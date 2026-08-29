"""Isolated execution of a case's private behavioral tests."""

from dataclasses import dataclass
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from evidencepatch.case_validation import validate_case
from evidencepatch.hidden_target import TARGET_REPO_ENV
from evidencepatch.repo_diff import compare_repositories


@dataclass(frozen=True)
class HiddenBehaviorResult:
    """Structured outcome from one isolated hidden-test subprocess."""

    passed: bool
    tests_total: int
    tests_passed: int
    tests_failed: int
    tests_errors: int
    tests_skipped: int
    returncode: int | None
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.passed, bool):
            raise ValueError("HiddenBehaviorResult passed must be a boolean")
        count_fields = (
            "tests_total",
            "tests_passed",
            "tests_failed",
            "tests_errors",
            "tests_skipped",
        )
        for field in count_fields:
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"HiddenBehaviorResult {field} must be a non-negative integer")
        counted = (
            self.tests_passed
            + self.tests_failed
            + self.tests_errors
            + self.tests_skipped
        )
        if counted != self.tests_total:
            raise ValueError("HiddenBehaviorResult test counts must sum to tests_total")
        if (
            self.returncode is not None
            and (isinstance(self.returncode, bool) or not isinstance(self.returncode, int))
        ):
            raise ValueError("HiddenBehaviorResult returncode must be an integer or None")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("HiddenBehaviorResult detail must be a non-empty string")


def _execution_failure(detail: str, returncode: int | None) -> HiddenBehaviorResult:
    """Create a zero-count execution-level failure result."""
    return HiddenBehaviorResult(False, 0, 0, 0, 0, 0, returncode, detail)


def _resolve_pytest_executable() -> str:
    """Resolve pytest from PATH or raise an evaluator-environment error."""
    executable = shutil.which("pytest")
    if not executable:
        raise RuntimeError(
            "Hidden evaluator environment has no pytest executable available on PATH"
        )
    return executable


def _bounded_process_output(stderr: str, stdout: str, limit: int = 400) -> str:
    """Return a bounded, whitespace-normalized subprocess diagnostic."""
    selected = stderr if stderr.strip() else stdout
    normalized = " ".join(selected.split())
    if not normalized:
        return "no subprocess diagnostic was available"
    if len(normalized) > limit:
        return normalized[: limit - 3] + "..."
    return normalized


def _parse_junit(
    report: Path,
    returncode: int,
    *,
    stdout: str,
    stderr: str,
) -> HiddenBehaviorResult:
    """Parse pytest JUnit counts into a behavioral result."""
    if not report.is_file():
        diagnostic = _bounded_process_output(stderr, stdout)
        return _execution_failure(
            "Hidden pytest JUnit report was not created; "
            f"subprocess diagnostic: {diagnostic}",
            returncode,
        )
    try:
        root = ET.parse(report).getroot()
    except (ET.ParseError, OSError) as error:
        return _execution_failure(
            f"Hidden pytest JUnit report could not be parsed: {type(error).__name__}",
            returncode,
        )

    if root.tag == "testsuite":
        suites = [root]
    elif root.tag == "testsuites":
        suites = list(root.findall("testsuite"))
    else:
        return _execution_failure(
            f"Hidden pytest JUnit report has unsupported root element: {root.tag}",
            returncode,
        )
    if not suites:
        return _execution_failure("Hidden pytest JUnit report contains no test suite", returncode)

    try:
        total = sum(int(suite.attrib.get("tests", "0")) for suite in suites)
        failed = sum(int(suite.attrib.get("failures", "0")) for suite in suites)
        errors = sum(int(suite.attrib.get("errors", "0")) for suite in suites)
        skipped = sum(int(suite.attrib.get("skipped", "0")) for suite in suites)
    except (TypeError, ValueError):
        return _execution_failure(
            "Hidden pytest JUnit report contains invalid count values", returncode
        )
    passed_count = total - failed - errors - skipped
    if min(total, failed, errors, skipped, passed_count) < 0:
        return _execution_failure(
            "Hidden pytest JUnit report contains inconsistent test counts", returncode
        )

    passed = returncode == 0 and total > 0 and failed == 0 and errors == 0
    return HiddenBehaviorResult(
        passed=passed,
        tests_total=total,
        tests_passed=passed_count,
        tests_failed=failed,
        tests_errors=errors,
        tests_skipped=skipped,
        returncode=returncode,
        detail="Hidden pytest execution completed and JUnit counts were parsed",
    )


def run_hidden_behavior(
    case_dir: Path,
    target_repo: Path,
    *,
    timeout_seconds: float = 30.0,
) -> HiddenBehaviorResult:
    """Run one case's hidden tests against a validated target repository."""
    validate_case(case_dir)
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise ValueError("timeout_seconds must be a positive finite number")

    compare_repositories(case_dir / "repo", target_repo)

    hidden_dir = case_dir / "hidden"
    hidden_tests = sorted(hidden_dir.glob("test_*.py"))
    if not hidden_tests:
        raise ValueError(f"No hidden test files found under: {hidden_dir}")
    for hidden_test in hidden_tests:
        if hidden_test.is_symlink():
            raise ValueError(f"Hidden test file must not be a symlink: {hidden_test}")
        if not hidden_test.is_file():
            raise ValueError(f"Hidden test path is not a regular file: {hidden_test}")

    environment = os.environ.copy()
    environment[TARGET_REPO_ENV] = str(target_repo.resolve())
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["PYTEST_ADDOPTS"] = ""
    environment.pop("PYTHONPATH", None)
    project_root = Path(__file__).resolve().parents[1]
    pytest_executable = _resolve_pytest_executable()

    with tempfile.TemporaryDirectory(prefix="evidencepatch-hidden-") as temporary:
        report = Path(temporary) / "junit.xml"
        command = [
            pytest_executable,
            *(str(path.resolve()) for path in hidden_tests),
            "-q",
            "-p",
            "no:cacheprovider",
            "--disable-warnings",
            "--tb=short",
            f"--junitxml={report}",
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=project_root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return _execution_failure(
                f"Hidden pytest execution timed out after {timeout_seconds:g} seconds",
                None,
            )
        return _parse_junit(
            report,
            completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
