"""Immutable generic result containers for EvidencePatch evaluation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationCheck:
    """One named evaluation outcome with a human-readable detail."""

    name: str
    passed: bool
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("EvaluationCheck name must be a non-empty string")
        if not isinstance(self.passed, bool):
            raise ValueError("EvaluationCheck passed must be a boolean")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("EvaluationCheck detail must be a non-empty string")


@dataclass(frozen=True)
class CaseEvaluation:
    """Ordered evaluation checks for one benchmark case."""

    case_id: str
    checks: tuple[EvaluationCheck, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id.strip():
            raise ValueError("CaseEvaluation case_id must be a non-empty string")
        if not isinstance(self.checks, tuple) or not self.checks:
            raise ValueError("CaseEvaluation checks must be a non-empty tuple")
        if any(not isinstance(check, EvaluationCheck) for check in self.checks):
            raise ValueError("CaseEvaluation checks must contain EvaluationCheck values")
        names = [check.name for check in self.checks]
        if len(set(names)) != len(names):
            raise ValueError("CaseEvaluation check names must be unique")

    @property
    def passed(self) -> bool:
        """Return whether every check passed."""
        return all(check.passed for check in self.checks)

    @property
    def failed_checks(self) -> tuple[EvaluationCheck, ...]:
        """Return failed checks in their original order."""
        return tuple(check for check in self.checks if not check.passed)

    def get_check(self, name: str) -> EvaluationCheck:
        """Return a check by name or raise a clear KeyError."""
        for check in self.checks:
            if check.name == name:
                return check
        raise KeyError(f"No evaluation check named {name!r} for case {self.case_id!r}")
