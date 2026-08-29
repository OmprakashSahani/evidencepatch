"""Generic aggregation of already-computed case evaluations."""

from dataclasses import dataclass

from evidencepatch.evaluation_types import CaseEvaluation


@dataclass(frozen=True)
class CheckMetric:
    """Aggregate pass count and rate for one named case check."""

    name: str
    passed_cases: int
    total_cases: int

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("CheckMetric name must be a non-empty string")
        if (
            isinstance(self.passed_cases, bool)
            or not isinstance(self.passed_cases, int)
            or self.passed_cases < 0
        ):
            raise ValueError("CheckMetric passed_cases must be a non-negative integer")
        if (
            isinstance(self.total_cases, bool)
            or not isinstance(self.total_cases, int)
            or self.total_cases <= 0
        ):
            raise ValueError("CheckMetric total_cases must be a positive integer")
        if self.passed_cases > self.total_cases:
            raise ValueError("CheckMetric passed_cases must not exceed total_cases")

    @property
    def rate(self) -> float:
        """Return the unrounded per-check pass rate."""
        return self.passed_cases / self.total_cases


@dataclass(frozen=True)
class BenchmarkEvaluation:
    """Aggregate complete-case and per-check benchmark outcomes."""

    cases: tuple[CaseEvaluation, ...]
    check_metrics: tuple[CheckMetric, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.cases, tuple) or not self.cases:
            raise ValueError("BenchmarkEvaluation cases must be a non-empty tuple")
        if any(not isinstance(case, CaseEvaluation) for case in self.cases):
            raise ValueError("BenchmarkEvaluation cases must contain CaseEvaluation values")
        case_ids = [case.case_id for case in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("BenchmarkEvaluation case IDs must be unique")

        common_order = tuple(check.name for check in self.cases[0].checks)
        for case in self.cases[1:]:
            order = tuple(check.name for check in case.checks)
            if order != common_order:
                raise ValueError(
                    "Every CaseEvaluation must use identical check names in the same order"
                )

        if not isinstance(self.check_metrics, tuple) or not self.check_metrics:
            raise ValueError(
                "BenchmarkEvaluation check_metrics must be a non-empty tuple"
            )
        if any(not isinstance(metric, CheckMetric) for metric in self.check_metrics):
            raise ValueError(
                "BenchmarkEvaluation check_metrics must contain CheckMetric values"
            )
        metric_names = tuple(metric.name for metric in self.check_metrics)
        if len(set(metric_names)) != len(metric_names):
            raise ValueError("BenchmarkEvaluation metric names must be unique")
        if metric_names != common_order:
            raise ValueError(
                "BenchmarkEvaluation metric names must match case check order"
            )

    @property
    def total_cases(self) -> int:
        """Return the number of evaluated cases."""
        return len(self.cases)

    @property
    def verified_successes(self) -> int:
        """Count cases where every check passed."""
        return sum(case.passed for case in self.cases)

    @property
    def vusr(self) -> float:
        """Return strict Verified Update Success Rate."""
        return self.verified_successes / self.total_cases

    @property
    def verified_failures(self) -> int:
        """Count cases that failed at least one check."""
        return self.total_cases - self.verified_successes

    @property
    def successful_cases(self) -> tuple[CaseEvaluation, ...]:
        """Return completely successful cases in input order."""
        return tuple(case for case in self.cases if case.passed)

    @property
    def failed_cases(self) -> tuple[CaseEvaluation, ...]:
        """Return cases with any failed check in input order."""
        return tuple(case for case in self.cases if not case.passed)

    def get_check_metric(self, name: str) -> CheckMetric:
        """Return a named check metric or raise a clear KeyError."""
        for metric in self.check_metrics:
            if metric.name == name:
                return metric
        raise KeyError(f"No benchmark check metric named {name!r}")


def aggregate_case_evaluations(
    evaluations: tuple[CaseEvaluation, ...],
) -> BenchmarkEvaluation:
    """Aggregate ordered case evaluations into strict and diagnostic metrics."""
    if not isinstance(evaluations, tuple) or not evaluations:
        raise ValueError("evaluations must be a non-empty tuple")
    if any(not isinstance(case, CaseEvaluation) for case in evaluations):
        raise ValueError("evaluations must contain CaseEvaluation values")
    case_ids = [case.case_id for case in evaluations]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("evaluation case IDs must be unique")

    check_names = tuple(check.name for check in evaluations[0].checks)
    if any(
        tuple(check.name for check in case.checks) != check_names
        for case in evaluations[1:]
    ):
        raise ValueError(
            "Every CaseEvaluation must use identical check names in the same order"
        )
    metrics = tuple(
        CheckMetric(
            name=name,
            passed_cases=sum(case.checks[index].passed for case in evaluations),
            total_cases=len(evaluations),
        )
        for index, name in enumerate(check_names)
    )
    return BenchmarkEvaluation(cases=evaluations, check_metrics=metrics)
