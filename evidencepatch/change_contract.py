"""Structured evidence governance for executable clinical-software changes."""

from dataclasses import dataclass
from enum import Enum


class EvidenceAuthority(Enum):
    """Authority classification for one evidence item."""

    AUTHORITATIVE = "AUTHORITATIVE"
    NON_AUTHORITATIVE = "NON_AUTHORITATIVE"
    DRAFT = "DRAFT"
    UNKNOWN = "UNKNOWN"


class EvidenceStatus(Enum):
    """Lifecycle status for one evidence item."""

    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"
    PROVISIONAL = "PROVISIONAL"
    UNKNOWN = "UNKNOWN"


class ChangeAction(Enum):
    """Permitted governance outcomes for a structured contract."""

    PATCH = "PATCH"
    NO_PATCH = "NO_PATCH"
    ESCALATE = "ESCALATE"


@dataclass(frozen=True)
class EvidenceAssessment:
    """Structured authority and change-pressure assessment of evidence."""

    evidence_id: str
    authority: EvidenceAuthority
    status: EvidenceStatus
    proposes_executable_change: bool
    conflicts_with_current_authority: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.evidence_id, str)
            or not self.evidence_id
            or self.evidence_id != self.evidence_id.strip()
        ):
            raise ValueError("evidence_id must be a non-empty stripped string")
        if not isinstance(self.authority, EvidenceAuthority):
            raise ValueError("authority must be an EvidenceAuthority")
        if not isinstance(self.status, EvidenceStatus):
            raise ValueError("status must be an EvidenceStatus")
        for field in (
            "proposes_executable_change",
            "conflicts_with_current_authority",
        ):
            if not isinstance(getattr(self, field), bool):
                raise ValueError(f"{field} must be a boolean")


@dataclass(frozen=True)
class ClinicalChangeContract:
    """Structured contract describing evidence state and semantic change."""

    schema_version: int
    evidence: tuple[EvidenceAssessment, ...]
    executable_behavior_change: bool
    semantic_equivalence: bool
    unresolved_conflict: bool
    ambiguous_or_incomplete: bool
    rationale: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != 1
        ):
            raise ValueError("schema_version must be integer 1")
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise ValueError("evidence must be a non-empty tuple")
        if any(not isinstance(item, EvidenceAssessment) for item in self.evidence):
            raise ValueError("evidence must contain EvidenceAssessment values")
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence IDs must be unique")
        for field in (
            "executable_behavior_change",
            "semantic_equivalence",
            "unresolved_conflict",
            "ambiguous_or_incomplete",
        ):
            if not isinstance(getattr(self, field), bool):
                raise ValueError(f"{field} must be a boolean")
        if (
            not isinstance(self.rationale, str)
            or not self.rationale
            or self.rationale != self.rationale.strip()
        ):
            raise ValueError("rationale must be a non-empty stripped string")
        if self.executable_behavior_change and self.semantic_equivalence:
            raise ValueError(
                "executable_behavior_change and semantic_equivalence cannot both be true"
            )


def current_authoritative_evidence(
    contract: ClinicalChangeContract,
) -> tuple[EvidenceAssessment, ...]:
    """Return current controlling authoritative evidence in contract order."""
    return tuple(
        item
        for item in contract.evidence
        if item.authority is EvidenceAuthority.AUTHORITATIVE
        and item.status is EvidenceStatus.CURRENT
    )


def unresolved_change_pressure(contract: ClinicalChangeContract) -> bool:
    """Return whether change pressure lacks a clean authoritative basis."""
    unresolved_authorities = {
        EvidenceAuthority.NON_AUTHORITATIVE,
        EvidenceAuthority.DRAFT,
        EvidenceAuthority.UNKNOWN,
    }
    unresolved_statuses = {EvidenceStatus.PROVISIONAL, EvidenceStatus.UNKNOWN}
    return any(
        item.proposes_executable_change
        and (
            item.authority in unresolved_authorities
            or item.status in unresolved_statuses
            or item.conflicts_with_current_authority
        )
        for item in contract.evidence
    )


def decide_change_action(contract: ClinicalChangeContract) -> ChangeAction:
    """Apply deterministic, fail-closed governance precedence."""
    current_authority = current_authoritative_evidence(contract)
    if (
        contract.unresolved_conflict
        or contract.ambiguous_or_incomplete
        or unresolved_change_pressure(contract)
        or (contract.executable_behavior_change and not current_authority)
    ):
        return ChangeAction.ESCALATE
    if contract.executable_behavior_change and current_authority:
        return ChangeAction.PATCH
    if contract.semantic_equivalence:
        return ChangeAction.NO_PATCH
    if (
        not contract.executable_behavior_change
        and not any(item.proposes_executable_change for item in contract.evidence)
    ):
        return ChangeAction.NO_PATCH
    return ChangeAction.ESCALATE


def requires_human_review(action: ChangeAction) -> bool:
    """Return the workflow human-review policy for an action."""
    if not isinstance(action, ChangeAction):
        raise ValueError("action must be a ChangeAction")
    return action in {ChangeAction.PATCH, ChangeAction.ESCALATE}
