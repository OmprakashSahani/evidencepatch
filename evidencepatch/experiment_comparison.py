"""Deterministic comparison of saved baseline and advanced experiment summaries."""

from dataclasses import dataclass
import json
from json import JSONDecodeError
import math
from pathlib import Path


@dataclass(frozen=True)
class CheckMetricDelta:
    """Observed change in one ordered evaluation-check metric."""

    name: str
    baseline_passed_cases: int
    advanced_passed_cases: int
    total_cases: int
    baseline_rate: float
    advanced_rate: float
    absolute_delta: float
    percentage_point_delta: float

    def __post_init__(self) -> None:
        _stripped(self.name, "name")
        for value, field in (
            (self.baseline_passed_cases, "baseline_passed_cases"),
            (self.advanced_passed_cases, "advanced_passed_cases"),
        ):
            _integer(value, field, minimum=0)
        _integer(self.total_cases, "total_cases", minimum=1)
        if max(self.baseline_passed_cases, self.advanced_passed_cases) > self.total_cases:
            raise ValueError("passed case counts must not exceed total_cases")
        for value, field in (
            (self.baseline_rate, "baseline_rate"),
            (self.advanced_rate, "advanced_rate"),
            (self.absolute_delta, "absolute_delta"),
            (self.percentage_point_delta, "percentage_point_delta"),
        ):
            _finite(value, field)
        if self.baseline_rate != self.baseline_passed_cases / self.total_cases:
            raise ValueError("baseline_rate is inconsistent with counts")
        if self.advanced_rate != self.advanced_passed_cases / self.total_cases:
            raise ValueError("advanced_rate is inconsistent with counts")
        if self.absolute_delta != self.advanced_rate - self.baseline_rate:
            raise ValueError("absolute_delta is inconsistent with rates")
        if self.percentage_point_delta != 100.0 * self.absolute_delta:
            raise ValueError("percentage_point_delta is inconsistent with absolute_delta")


@dataclass(frozen=True)
class CaseOutcomeDelta:
    """Observed complete-case outcome transition for one case."""

    case_id: str
    baseline_verified_success: bool
    advanced_verified_success: bool
    baseline_failed_checks: tuple[str, ...]
    advanced_failed_checks: tuple[str, ...]

    def __post_init__(self) -> None:
        _stripped(self.case_id, "case_id")
        for value, field in (
            (self.baseline_verified_success, "baseline_verified_success"),
            (self.advanced_verified_success, "advanced_verified_success"),
        ):
            if not isinstance(value, bool):
                raise ValueError(f"{field} must be a boolean")
        _check_names(self.baseline_failed_checks, "baseline_failed_checks")
        _check_names(self.advanced_failed_checks, "advanced_failed_checks")

    @property
    def outcome(self) -> str:
        if not self.baseline_verified_success and self.advanced_verified_success:
            return "IMPROVED"
        if self.baseline_verified_success and not self.advanced_verified_success:
            return "REGRESSED"
        if self.baseline_verified_success:
            return "UNCHANGED_SUCCESS"
        return "UNCHANGED_FAILURE"


@dataclass(frozen=True)
class ExperimentComparison:
    """Validated measured comparison of two frozen experiment summaries."""

    baseline_summary_path: Path
    advanced_summary_path: Path
    baseline_model: str
    advanced_model: str
    baseline_total_cases: int
    advanced_total_cases: int
    baseline_verified_successes: int
    advanced_verified_successes: int
    baseline_verified_failures: int
    advanced_verified_failures: int
    baseline_vusr: float
    advanced_vusr: float
    vusr_absolute_delta: float
    vusr_percentage_point_delta: float
    baseline_total_codex_calls: int
    advanced_total_codex_calls: int
    codex_call_delta: int
    codex_call_ratio: float
    baseline_total_duration_seconds: float
    advanced_total_duration_seconds: float
    duration_delta_seconds: float
    duration_ratio: float
    failure_reduction_count: int
    failure_reduction_rate: float | None
    check_metric_deltas: tuple[CheckMetricDelta, ...]
    case_outcome_deltas: tuple[CaseOutcomeDelta, ...]

    def __post_init__(self) -> None:
        for value, field in (
            (self.baseline_summary_path, "baseline_summary_path"),
            (self.advanced_summary_path, "advanced_summary_path"),
        ):
            if not isinstance(value, Path):
                raise ValueError(f"{field} must be a pathlib.Path")
        _stripped(self.baseline_model, "baseline_model")
        _stripped(self.advanced_model, "advanced_model")
        for value, field, minimum in (
            (self.baseline_total_cases, "baseline_total_cases", 1),
            (self.advanced_total_cases, "advanced_total_cases", 1),
            (self.baseline_verified_successes, "baseline_verified_successes", 0),
            (self.advanced_verified_successes, "advanced_verified_successes", 0),
            (self.baseline_verified_failures, "baseline_verified_failures", 0),
            (self.advanced_verified_failures, "advanced_verified_failures", 0),
            (self.baseline_total_codex_calls, "baseline_total_codex_calls", 1),
            (self.advanced_total_codex_calls, "advanced_total_codex_calls", 0),
        ):
            _integer(value, field, minimum=minimum)
        _integer(self.codex_call_delta, "codex_call_delta")
        _integer(self.failure_reduction_count, "failure_reduction_count")
        for value, field in (
            (self.baseline_vusr, "baseline_vusr"),
            (self.advanced_vusr, "advanced_vusr"),
            (self.vusr_absolute_delta, "vusr_absolute_delta"),
            (self.vusr_percentage_point_delta, "vusr_percentage_point_delta"),
            (self.codex_call_ratio, "codex_call_ratio"),
            (self.baseline_total_duration_seconds, "baseline_total_duration_seconds"),
            (self.advanced_total_duration_seconds, "advanced_total_duration_seconds"),
            (self.duration_delta_seconds, "duration_delta_seconds"),
            (self.duration_ratio, "duration_ratio"),
        ):
            _finite(value, field)
        if self.failure_reduction_rate is not None:
            _finite(self.failure_reduction_rate, "failure_reduction_rate")
        if not isinstance(self.check_metric_deltas, tuple) or not self.check_metric_deltas:
            raise ValueError("check_metric_deltas must be a non-empty tuple")
        if any(not isinstance(item, CheckMetricDelta) for item in self.check_metric_deltas):
            raise ValueError("check_metric_deltas must contain CheckMetricDelta values")
        if not isinstance(self.case_outcome_deltas, tuple) or not self.case_outcome_deltas:
            raise ValueError("case_outcome_deltas must be a non-empty tuple")
        if any(not isinstance(item, CaseOutcomeDelta) for item in self.case_outcome_deltas):
            raise ValueError("case_outcome_deltas must contain CaseOutcomeDelta values")


def _stripped(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field} must be a non-empty stripped string")
    return value


def _integer(value: object, field: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return value


def _finite(value: object, field: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return value


def _check_names(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ValueError(f"{field} must be a tuple")
    for item in value:
        _stripped(item, field)
    if len(set(value)) != len(value):
        raise ValueError(f"{field} must contain unique values")
    return value


def _load_summary(path: object, name: str) -> dict[str, object]:
    if not isinstance(path, Path):
        raise ValueError(f"{name} must be a pathlib.Path")
    if path.is_symlink():
        raise ValueError(f"{name} must not be a symlink")
    if not path.exists():
        raise FileNotFoundError(f"{name} does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"{name} must be a regular file")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{name} is not valid UTF-8") from error
    try:
        value = json.loads(text)
    except JSONDecodeError as error:
        raise ValueError(f"{name} contains invalid JSON: {error.msg}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain a JSON object")
    _reject_invalid_numbers(value, name)
    return value


def _reject_invalid_numbers(value: object, context: str, field: str = "") -> None:
    """Reject non-finite numbers and negative duration fields anywhere in JSON."""
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_invalid_numbers(item, context, str(key))
    elif isinstance(value, list):
        for item in value:
            _reject_invalid_numbers(item, context, field)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{context} contains a non-finite numeric value")
    elif (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and "duration" in field
        and value < 0
    ):
        raise ValueError(f"{context} contains a negative duration")


def _require(summary: dict[str, object], field: str, context: str) -> object:
    if field not in summary:
        raise ValueError(f"{context} is missing {field}")
    return summary[field]


def _validate_cases(summary: dict[str, object], total: int, context: str) -> list[dict[str, object]]:
    cases = _require(summary, "cases", context)
    if not isinstance(cases, list) or len(cases) != total:
        raise ValueError(f"{context} cases must be a list with total_cases entries")
    parsed: list[dict[str, object]] = []
    ids: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"{context} cases[{index}] must be an object")
        case_id = _stripped(_require(case, "case_id", context), "case_id")
        success = _require(case, "verified_success", context)
        if not isinstance(success, bool):
            raise ValueError("verified_success must be a boolean")
        failed = _require(case, "failed_checks", context)
        if not isinstance(failed, list):
            raise ValueError("failed_checks must be a list")
        failed_tuple = tuple(failed)
        _check_names(failed_tuple, "failed_checks")
        ids.append(case_id)
        parsed.append({**case, "case_id": case_id, "verified_success": success, "failed_checks": failed_tuple})
    if len(set(ids)) != len(ids):
        raise ValueError(f"{context} case IDs must be unique")
    return parsed


def _validate_metrics(summary: dict[str, object], total: int, context: str) -> list[dict[str, object]]:
    metrics = _require(summary, "check_metrics", context)
    if not isinstance(metrics, list) or not metrics:
        raise ValueError(f"{context} check_metrics must be a non-empty list")
    parsed: list[dict[str, object]] = []
    names: list[str] = []
    for metric in metrics:
        if not isinstance(metric, dict):
            raise ValueError(f"{context} check metric must be an object")
        name = _stripped(_require(metric, "name", context), "metric name")
        passed = _integer(_require(metric, "passed_cases", context), "passed_cases", 0)
        metric_total = _integer(_require(metric, "total_cases", context), "metric total_cases", 1)
        if metric_total != total or passed > total:
            raise ValueError(f"{context} metric totals are inconsistent")
        rate = _finite(_require(metric, "rate", context), "metric rate")
        if rate != passed / total:
            raise ValueError(f"{context} metric rate is inconsistent")
        names.append(name)
        parsed.append({"name": name, "passed_cases": passed, "total_cases": total, "rate": rate})
    if len(set(names)) != len(names):
        raise ValueError(f"{context} metric names must be unique")
    return parsed


def _common_summary(summary: dict[str, object], experiment: str, context: str):
    if _require(summary, "schema_version", context) != 1 or isinstance(summary["schema_version"], bool):
        raise ValueError(f"{context} schema_version must be integer 1")
    if _require(summary, "experiment", context) != experiment:
        raise ValueError(f"{context} experiment must be {experiment!r}")
    model = _stripped(_require(summary, "model", context), "model")
    total = _integer(_require(summary, "total_cases", context), "total_cases", 1)
    successes = _integer(_require(summary, "verified_successes", context), "verified_successes", 0)
    failures = _integer(_require(summary, "verified_failures", context), "verified_failures", 0)
    if successes + failures != total:
        raise ValueError(f"{context} successes and failures must sum to total_cases")
    vusr = _finite(_require(summary, "vusr", context), "vusr")
    if vusr != successes / total:
        raise ValueError(f"{context} vusr is inconsistent with verified_successes")
    cases = _validate_cases(summary, total, context)
    metrics = _validate_metrics(summary, total, context)
    return model, total, successes, failures, vusr, cases, metrics


def compare_experiment_summaries(
    baseline_summary_path: Path,
    advanced_summary_path: Path,
) -> ExperimentComparison:
    """Compare two already-saved, strictly comparable experiment summaries."""
    baseline = _load_summary(baseline_summary_path, "baseline_summary_path")
    advanced = _load_summary(advanced_summary_path, "advanced_summary_path")
    b = _common_summary(baseline, "plain_codex_baseline", "baseline summary")
    a = _common_summary(advanced, "evidencepatch_advanced", "advanced summary")
    b_model, b_total, b_success, b_failure, b_vusr, b_cases, b_metrics = b
    a_model, a_total, a_success, a_failure, a_vusr, a_cases, a_metrics = a
    if b_model != a_model:
        raise ValueError("baseline and advanced summaries must use the same model")
    if b_total != a_total:
        raise ValueError("baseline and advanced summaries must have the same total_cases")
    if [case["case_id"] for case in b_cases] != [case["case_id"] for case in a_cases]:
        raise ValueError("baseline and advanced case IDs must match in the same order")
    if [metric["name"] for metric in b_metrics] != [metric["name"] for metric in a_metrics]:
        raise ValueError("baseline and advanced check names must match in the same order")

    baseline_calls = len(b_cases)
    advanced_calls = _integer(_require(advanced, "total_codex_calls", "advanced summary"), "total_codex_calls", 0)
    observed_advanced_calls = sum(
        _integer(_require(case, "codex_call_count", "advanced case"), "codex_call_count", 0)
        for case in a_cases
    )
    if advanced_calls != observed_advanced_calls:
        raise ValueError("advanced total_codex_calls does not match case rows")
    baseline_duration = _finite(
        _require(baseline, "total_duration_seconds", "baseline summary"),
        "baseline total_duration_seconds", 0,
    )
    advanced_duration = _finite(
        _require(advanced, "total_codex_duration_seconds", "advanced summary"),
        "advanced total_codex_duration_seconds", 0,
    )
    if baseline_duration <= 0:
        raise ValueError("baseline total duration must be greater than zero")

    metric_deltas = tuple(
        CheckMetricDelta(
            name=bm["name"],
            baseline_passed_cases=bm["passed_cases"],
            advanced_passed_cases=am["passed_cases"],
            total_cases=b_total,
            baseline_rate=bm["rate"],
            advanced_rate=am["rate"],
            absolute_delta=am["rate"] - bm["rate"],
            percentage_point_delta=100.0 * (am["rate"] - bm["rate"]),
        )
        for bm, am in zip(b_metrics, a_metrics, strict=True)
    )
    case_deltas = tuple(
        CaseOutcomeDelta(
            case_id=bc["case_id"],
            baseline_verified_success=bc["verified_success"],
            advanced_verified_success=ac["verified_success"],
            baseline_failed_checks=bc["failed_checks"],
            advanced_failed_checks=ac["failed_checks"],
        )
        for bc, ac in zip(b_cases, a_cases, strict=True)
    )
    vusr_delta = a_vusr - b_vusr
    failure_reduction = b_failure - a_failure
    return ExperimentComparison(
        baseline_summary_path=baseline_summary_path.resolve(),
        advanced_summary_path=advanced_summary_path.resolve(),
        baseline_model=b_model,
        advanced_model=a_model,
        baseline_total_cases=b_total,
        advanced_total_cases=a_total,
        baseline_verified_successes=b_success,
        advanced_verified_successes=a_success,
        baseline_verified_failures=b_failure,
        advanced_verified_failures=a_failure,
        baseline_vusr=b_vusr,
        advanced_vusr=a_vusr,
        vusr_absolute_delta=vusr_delta,
        vusr_percentage_point_delta=100.0 * vusr_delta,
        baseline_total_codex_calls=baseline_calls,
        advanced_total_codex_calls=advanced_calls,
        codex_call_delta=advanced_calls - baseline_calls,
        codex_call_ratio=advanced_calls / baseline_calls,
        baseline_total_duration_seconds=baseline_duration,
        advanced_total_duration_seconds=advanced_duration,
        duration_delta_seconds=advanced_duration - baseline_duration,
        duration_ratio=advanced_duration / baseline_duration,
        failure_reduction_count=failure_reduction,
        failure_reduction_rate=(failure_reduction / b_failure if b_failure else None),
        check_metric_deltas=metric_deltas,
        case_outcome_deltas=case_deltas,
    )


def comparison_to_mapping(comparison: ExperimentComparison) -> dict[str, object]:
    """Return the exact deterministic JSON-ready comparison structure."""
    if not isinstance(comparison, ExperimentComparison):
        raise ValueError("comparison must be an ExperimentComparison")
    return {
        "schema_version": 1,
        "comparison": "plain_codex_baseline_vs_evidencepatch_advanced",
        "baseline": {
            "model": comparison.baseline_model,
            "total_cases": comparison.baseline_total_cases,
            "verified_successes": comparison.baseline_verified_successes,
            "verified_failures": comparison.baseline_verified_failures,
            "vusr": comparison.baseline_vusr,
            "total_codex_calls": comparison.baseline_total_codex_calls,
            "total_codex_duration_seconds": comparison.baseline_total_duration_seconds,
        },
        "advanced": {
            "model": comparison.advanced_model,
            "total_cases": comparison.advanced_total_cases,
            "verified_successes": comparison.advanced_verified_successes,
            "verified_failures": comparison.advanced_verified_failures,
            "vusr": comparison.advanced_vusr,
            "total_codex_calls": comparison.advanced_total_codex_calls,
            "total_codex_duration_seconds": comparison.advanced_total_duration_seconds,
        },
        "improvement": {
            "vusr_absolute_delta": comparison.vusr_absolute_delta,
            "vusr_percentage_point_delta": comparison.vusr_percentage_point_delta,
            "failure_reduction_count": comparison.failure_reduction_count,
            "failure_reduction_rate": comparison.failure_reduction_rate,
        },
        "cost_tradeoff": {
            "codex_call_delta": comparison.codex_call_delta,
            "codex_call_ratio": comparison.codex_call_ratio,
            "duration_delta_seconds": comparison.duration_delta_seconds,
            "duration_ratio": comparison.duration_ratio,
        },
        "check_metric_deltas": [
            {
                "name": item.name,
                "baseline_passed_cases": item.baseline_passed_cases,
                "advanced_passed_cases": item.advanced_passed_cases,
                "total_cases": item.total_cases,
                "baseline_rate": item.baseline_rate,
                "advanced_rate": item.advanced_rate,
                "absolute_delta": item.absolute_delta,
                "percentage_point_delta": item.percentage_point_delta,
            }
            for item in comparison.check_metric_deltas
        ],
        "case_outcome_deltas": [
            {
                "case_id": item.case_id,
                "baseline_verified_success": item.baseline_verified_success,
                "advanced_verified_success": item.advanced_verified_success,
                "baseline_failed_checks": list(item.baseline_failed_checks),
                "advanced_failed_checks": list(item.advanced_failed_checks),
                "outcome": item.outcome,
            }
            for item in comparison.case_outcome_deltas
        ],
    }


def _safe_output(path: object, content: str) -> Path:
    if not isinstance(path, Path):
        raise ValueError("output_path must be a pathlib.Path")
    if path.is_symlink():
        raise ValueError("output_path must not be a symlink")
    if path.exists():
        raise ValueError("output_path must not already exist")
    if not path.parent.exists() or not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("output parent must be an existing normal directory")
    path.write_text(content, encoding="utf-8")
    return path.resolve()


def write_comparison_json(comparison: ExperimentComparison, output_path: Path) -> Path:
    """Safely write deterministic comparison JSON without overwriting."""
    content = json.dumps(comparison_to_mapping(comparison), indent=2, sort_keys=True) + "\n"
    return _safe_output(output_path, content)


def comparison_to_markdown(comparison: ExperimentComparison) -> str:
    """Render a concise deterministic measured-improvement report."""
    if not isinstance(comparison, ExperimentComparison):
        raise ValueError("comparison must be an ExperimentComparison")
    reduction = (
        "not defined because the baseline had no failures"
        if comparison.failure_reduction_rate is None
        else f"{comparison.failure_reduction_rate * 100:.2f}%"
    )
    reliability_cases = [
        item for item in comparison.case_outcome_deltas
        if item.outcome != "UNCHANGED_SUCCESS"
    ]
    reliability_lines = [
        f"- `{item.case_id}` — {item.outcome}; baseline failed checks: "
        f"{', '.join(item.baseline_failed_checks) or 'none'}; advanced failed checks: "
        f"{', '.join(item.advanced_failed_checks) or 'none'}"
        for item in reliability_cases
    ] or ["- No improved, regressed, or unchanged-failure cases."]
    metric_rows = [
        f"| {item.name} | {item.baseline_passed_cases}/{item.total_cases} "
        f"({item.baseline_rate * 100:.2f}%) | {item.advanced_passed_cases}/{item.total_cases} "
        f"({item.advanced_rate * 100:.2f}%) | {item.percentage_point_delta:+.2f} pp |"
        for item in comparison.check_metric_deltas
    ]
    case_rows = [
        f"| {item.case_id} | {'PASS' if item.baseline_verified_success else 'FAIL'} | "
        f"{'PASS' if item.advanced_verified_success else 'FAIL'} | {item.outcome} |"
        for item in comparison.case_outcome_deltas
    ]
    if comparison.advanced_vusr > comparison.baseline_vusr:
        interpretation = "EvidencePatch improved strict Verified Update Success Rate on the same cases."
    elif comparison.advanced_vusr < comparison.baseline_vusr:
        interpretation = "EvidencePatch regressed on strict Verified Update Success Rate on the same cases."
    else:
        interpretation = "EvidencePatch showed no measured VUSR improvement on the same cases."
    if (
        comparison.advanced_total_codex_calls > comparison.baseline_total_codex_calls
        or comparison.advanced_total_duration_seconds > comparison.baseline_total_duration_seconds
    ):
        interpretation += " The reliability result came with higher model-compute cost."
    return "\n".join([
        "# EvidencePatch Measured Improvement", "", "## Primary Metric", "",
        f"Plain Codex baseline: {comparison.baseline_verified_successes}/{comparison.baseline_total_cases} ({comparison.baseline_vusr * 100:.2f}%)",
        f"EvidencePatch advanced: {comparison.advanced_verified_successes}/{comparison.advanced_total_cases} ({comparison.advanced_vusr * 100:.2f}%)",
        f"Absolute improvement: {comparison.vusr_percentage_point_delta:+.2f} percentage points", "",
        "## Reliability Breakdown", "",
        f"Baseline failures: {comparison.baseline_verified_failures}",
        f"Advanced failures: {comparison.advanced_verified_failures}",
        f"Failure reduction: {comparison.failure_reduction_count} ({reduction})", "",
        *reliability_lines, "", "## Cost Tradeoff", "",
        f"Baseline Codex calls: {comparison.baseline_total_codex_calls}",
        f"Advanced Codex calls: {comparison.advanced_total_codex_calls}",
        f"Call delta: {comparison.codex_call_delta:+d}; ratio: {comparison.codex_call_ratio:.2f}x",
        f"Baseline solver duration: {comparison.baseline_total_duration_seconds:.2f} seconds",
        f"Advanced solver duration: {comparison.advanced_total_duration_seconds:.2f} seconds",
        f"Duration delta: {comparison.duration_delta_seconds:+.2f} seconds; ratio: {comparison.duration_ratio:.2f}x",
        "The reliability gain used additional model invocations and solver time.", "",
        "## Per-Check Results", "", "| Check | Baseline | Advanced | Delta |",
        "| --- | ---: | ---: | ---: |", *metric_rows, "", "## Case-Level Changes", "",
        "| Case | Baseline | Advanced | Outcome |", "| --- | --- | --- | --- |", *case_rows, "",
        "## Interpretation", "", interpretation,
        " Results apply only to this benchmark and do not establish statistical significance.", "",
        "## Methodological Notes", "",
        "- The same benchmark case list and the same model were required for comparison.",
        "- Metrics came from saved frozen experiment summaries; this comparison does not rerun a solver.",
        "- The comparison layer reads no hidden ground truth.",
        "- VUSR is strict complete-case success.",
        "- Benchmark results do not establish clinical safety or real-world medical effectiveness.",
        "- The advanced workflow uses additional structured model calls, so the comparison is a reliability-versus-compute tradeoff rather than an equal-inference-budget comparison.",
        "",
    ])


def write_comparison_markdown(comparison: ExperimentComparison, output_path: Path) -> Path:
    """Safely write deterministic comparison Markdown without overwriting."""
    return _safe_output(output_path, comparison_to_markdown(comparison))


def write_comparison_report(
    baseline_summary_path: Path,
    advanced_summary_path: Path,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write comparison.json and comparison.md from two saved summaries."""
    if not isinstance(output_dir, Path):
        raise ValueError("output_dir must be a pathlib.Path")
    if output_dir.is_symlink() or not output_dir.exists() or not output_dir.is_dir():
        raise ValueError("output_dir must be an existing normal directory")
    json_path = output_dir / "comparison.json"
    markdown_path = output_dir / "comparison.md"
    if json_path.exists() or json_path.is_symlink() or markdown_path.exists() or markdown_path.is_symlink():
        raise ValueError("comparison report files must not already exist")
    comparison = compare_experiment_summaries(baseline_summary_path, advanced_summary_path)
    return (
        write_comparison_json(comparison, json_path),
        write_comparison_markdown(comparison, markdown_path),
    )
