from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.change_contract import (
    ChangeAction,
    ClinicalChangeContract,
    EvidenceAssessment,
    EvidenceAuthority,
    EvidenceStatus,
    current_authoritative_evidence,
    decide_change_action,
    requires_human_review,
    unresolved_change_pressure,
)


def _evidence(
    evidence_id="SYNTHETIC-SOURCE-A",
    *,
    authority=EvidenceAuthority.AUTHORITATIVE,
    status=EvidenceStatus.CURRENT,
    proposes_change=False,
    conflicts=False,
):
    return EvidenceAssessment(
        evidence_id=evidence_id,
        authority=authority,
        status=status,
        proposes_executable_change=proposes_change,
        conflicts_with_current_authority=conflicts,
    )


def _contract(
    evidence=None,
    *,
    executable_change=False,
    equivalent=False,
    conflict=False,
    ambiguous=False,
):
    return ClinicalChangeContract(
        schema_version=1,
        evidence=tuple(evidence or (_evidence(),)),
        executable_behavior_change=executable_change,
        semantic_equivalence=equivalent,
        unresolved_conflict=conflict,
        ambiguous_or_incomplete=ambiguous,
        rationale="Generic structured evidence assessment.",
    )


def test_authoritative_executable_change_is_patch_with_review():
    contract = _contract(
        (_evidence(proposes_change=True),), executable_change=True
    )

    action = decide_change_action(contract)

    assert action is ChangeAction.PATCH
    assert requires_human_review(action) is True


def test_non_authoritative_conflicting_pressure_escalates():
    contract = _contract(
        (
            _evidence("SYNTHETIC-CONTROLLING"),
            _evidence(
                "SYNTHETIC-OBSERVATION",
                authority=EvidenceAuthority.NON_AUTHORITATIVE,
                proposes_change=True,
                conflicts=True,
            ),
        )
    )

    action = decide_change_action(contract)

    assert action is ChangeAction.ESCALATE
    assert requires_human_review(action) is True


def test_draft_provisional_proposal_escalates():
    contract = _contract(
        (
            _evidence(
                authority=EvidenceAuthority.DRAFT,
                status=EvidenceStatus.PROVISIONAL,
                proposes_change=True,
            ),
        ),
        executable_change=True,
    )

    assert decide_change_action(contract) is ChangeAction.ESCALATE


def test_ambiguous_evidence_escalates():
    assert decide_change_action(_contract(ambiguous=True)) is ChangeAction.ESCALATE


def test_semantic_equivalence_is_no_patch_without_review():
    contract = _contract(equivalent=True)

    action = decide_change_action(contract)

    assert action is ChangeAction.NO_PATCH
    assert requires_human_review(action) is False


def test_clean_no_change_state_is_no_patch():
    assert decide_change_action(_contract()) is ChangeAction.NO_PATCH


def test_executable_change_without_current_authority_escalates():
    contract = _contract(
        (
            _evidence(
                authority=EvidenceAuthority.NON_AUTHORITATIVE,
                proposes_change=True,
            ),
        ),
        executable_change=True,
    )

    assert decide_change_action(contract) is ChangeAction.ESCALATE


def test_superseded_authority_is_not_controlling():
    contract = _contract(
        (
            _evidence(
                status=EvidenceStatus.SUPERSEDED,
                proposes_change=True,
            ),
        ),
        executable_change=True,
    )

    assert decide_change_action(contract) is ChangeAction.ESCALATE


def test_conflict_overrides_actionable_authoritative_change():
    contract = _contract(
        (_evidence(proposes_change=True),),
        executable_change=True,
        conflict=True,
    )

    assert decide_change_action(contract) is ChangeAction.ESCALATE


def test_ambiguity_overrides_semantic_equivalence():
    contract = _contract(equivalent=True, ambiguous=True)

    assert decide_change_action(contract) is ChangeAction.ESCALATE


def test_non_authoritative_no_change_evidence_does_not_force_escalation():
    contract = _contract(
        (
            _evidence("SYNTHETIC-CONTROLLING"),
            _evidence(
                "SYNTHETIC-CONTEXT",
                authority=EvidenceAuthority.NON_AUTHORITATIVE,
            ),
        )
    )

    assert decide_change_action(contract) is ChangeAction.NO_PATCH


def test_duplicate_evidence_ids_are_rejected():
    with pytest.raises(ValueError, match="IDs.*unique"):
        _contract((_evidence("SAME"), _evidence("SAME")))


def test_empty_evidence_is_rejected():
    with pytest.raises(ValueError, match="evidence.*non-empty"):
        ClinicalChangeContract(1, (), False, False, False, False, "rationale")


@pytest.mark.parametrize("version", [0, 2, True, "1"])
def test_invalid_schema_version_is_rejected(version):
    with pytest.raises(ValueError, match="schema_version"):
        ClinicalChangeContract(
            version, (_evidence(),), False, False, False, False, "rationale"
        )


def test_change_and_equivalence_cannot_both_be_true():
    with pytest.raises(ValueError, match="cannot both be true"):
        _contract(executable_change=True, equivalent=True)


@pytest.mark.parametrize(
    "field",
    [
        "executable_behavior_change",
        "semantic_equivalence",
        "unresolved_conflict",
        "ambiguous_or_incomplete",
    ],
)
@pytest.mark.parametrize("invalid", [1, 0, "true", None])
def test_contract_boolean_fields_reject_non_booleans(field, invalid):
    values = {
        "schema_version": 1,
        "evidence": (_evidence(),),
        "executable_behavior_change": False,
        "semantic_equivalence": False,
        "unresolved_conflict": False,
        "ambiguous_or_incomplete": False,
        "rationale": "rationale",
    }
    values[field] = invalid

    with pytest.raises(ValueError, match=f"{field}.*boolean"):
        ClinicalChangeContract(**values)


@pytest.mark.parametrize(
    "field",
    ["proposes_executable_change", "conflicts_with_current_authority"],
)
@pytest.mark.parametrize("invalid", [1, 0, "true", None])
def test_assessment_boolean_fields_reject_non_booleans(field, invalid):
    values = {
        "evidence_id": "SYNTHETIC-SOURCE",
        "authority": EvidenceAuthority.AUTHORITATIVE,
        "status": EvidenceStatus.CURRENT,
        "proposes_executable_change": False,
        "conflicts_with_current_authority": False,
    }
    values[field] = invalid

    with pytest.raises(ValueError, match=f"{field}.*boolean"):
        EvidenceAssessment(**values)


@pytest.mark.parametrize(
    ("field", "invalid", "message"),
    [
        ("authority", "AUTHORITATIVE", "EvidenceAuthority"),
        ("status", "CURRENT", "EvidenceStatus"),
    ],
)
def test_invalid_enum_types_are_rejected(field, invalid, message):
    values = {
        "evidence_id": "SYNTHETIC-SOURCE",
        "authority": EvidenceAuthority.AUTHORITATIVE,
        "status": EvidenceStatus.CURRENT,
        "proposes_executable_change": False,
        "conflicts_with_current_authority": False,
    }
    values[field] = invalid

    with pytest.raises(ValueError, match=message):
        EvidenceAssessment(**values)


def test_blank_evidence_id_is_rejected():
    with pytest.raises(ValueError, match="evidence_id.*non-empty"):
        _evidence("  ")


@pytest.mark.parametrize("evidence_id", [" SOURCE-A", "SOURCE-A "])
def test_evidence_id_with_surrounding_whitespace_is_rejected(evidence_id):
    with pytest.raises(ValueError, match="evidence_id.*stripped"):
        _evidence(evidence_id)


def test_blank_rationale_is_rejected():
    with pytest.raises(ValueError, match="rationale.*non-empty"):
        ClinicalChangeContract(
            1, (_evidence(),), False, False, False, False, "  "
        )


@pytest.mark.parametrize("rationale", [" rationale", "rationale "])
def test_rationale_with_surrounding_whitespace_is_rejected(rationale):
    with pytest.raises(ValueError, match="rationale.*stripped"):
        ClinicalChangeContract(
            1, (_evidence(),), False, False, False, False, rationale
        )


def test_whitespace_variant_cannot_coexist_with_canonical_evidence_id():
    canonical = _evidence("SOURCE-A")

    with pytest.raises(ValueError, match="evidence_id.*stripped"):
        _contract((canonical, _evidence(" SOURCE-A ")))


def test_current_authoritative_evidence_excludes_superseded_items():
    current = _evidence("CURRENT")
    superseded = _evidence("OLD", status=EvidenceStatus.SUPERSEDED)
    contextual = _evidence(
        "CONTEXT", authority=EvidenceAuthority.NON_AUTHORITATIVE
    )
    contract = _contract((superseded, current, contextual))

    assert current_authoritative_evidence(contract) == (current,)


@pytest.mark.parametrize(
    "assessment",
    [
        _evidence(
            authority=EvidenceAuthority.NON_AUTHORITATIVE,
            proposes_change=True,
        ),
        _evidence(authority=EvidenceAuthority.DRAFT, proposes_change=True),
        _evidence(status=EvidenceStatus.PROVISIONAL, proposes_change=True),
        _evidence(proposes_change=True, conflicts=True),
    ],
)
def test_unresolved_change_pressure_detects_unresolved_proposals(assessment):
    assert unresolved_change_pressure(_contract((assessment,))) is True


def test_unresolved_change_pressure_is_false_for_clean_authoritative_change():
    contract = _contract(
        (_evidence(proposes_change=True),), executable_change=True
    )

    assert unresolved_change_pressure(contract) is False


def test_fail_closed_for_unresolved_structured_state():
    contract = _contract((_evidence(proposes_change=True),))

    assert decide_change_action(contract) is ChangeAction.ESCALATE


def test_requires_human_review_rejects_invalid_action():
    with pytest.raises(ValueError, match="ChangeAction"):
        requires_human_review("PATCH")


def test_contract_dataclasses_are_immutable():
    assessment = _evidence()
    contract = _contract((assessment,))

    with pytest.raises(FrozenInstanceError):
        assessment.evidence_id = "different"
    with pytest.raises(FrozenInstanceError):
        contract.rationale = "different"
