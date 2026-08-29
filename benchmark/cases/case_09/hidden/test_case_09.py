import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.hidden_target import resolve_hidden_target_repo


CASE_REPOSITORY = resolve_hidden_target_repo(__file__)
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.continuation import is_avenoril_continuation_allowed
from medication_rules.initiation import is_avenoril_initiation_allowed


def test_initiation_allergy_contraindication_is_preserved():
    patient = {
        "avenoril_allergy": True,
        "marker_v": 64,
        "baseline_review_complete": True,
    }
    assert is_avenoril_initiation_allowed(patient) is False


def test_initiation_baseline_prerequisite_is_preserved():
    patient = {
        "avenoril_allergy": False,
        "marker_v": 64,
        "baseline_review_complete": False,
    }
    assert is_avenoril_initiation_allowed(patient) is False


def test_initiation_marker_v_64_is_allowed():
    patient = {
        "avenoril_allergy": False,
        "marker_v": 64,
        "baseline_review_complete": True,
    }
    assert is_avenoril_initiation_allowed(patient) is True


def test_initiation_marker_v_65_is_denied():
    patient = {
        "avenoril_allergy": False,
        "marker_v": 65,
        "baseline_review_complete": True,
    }
    assert is_avenoril_initiation_allowed(patient) is False


def test_initiation_marker_v_90_is_denied():
    patient = {
        "avenoril_allergy": False,
        "marker_v": 90,
        "baseline_review_complete": True,
    }
    assert is_avenoril_initiation_allowed(patient) is False


def test_continuation_allergy_contraindication_is_preserved():
    patient = {
        "avenoril_allergy": True,
        "marker_v": 64,
        "followup_current": True,
    }
    assert is_avenoril_continuation_allowed(patient) is False


def test_continuation_followup_prerequisite_is_preserved():
    patient = {
        "avenoril_allergy": False,
        "marker_v": 64,
        "followup_current": False,
    }
    assert is_avenoril_continuation_allowed(patient) is False


def test_continuation_marker_v_64_is_allowed():
    patient = {
        "avenoril_allergy": False,
        "marker_v": 64,
        "followup_current": True,
    }
    assert is_avenoril_continuation_allowed(patient) is True


def test_continuation_marker_v_65_is_denied():
    patient = {
        "avenoril_allergy": False,
        "marker_v": 65,
        "followup_current": True,
    }
    assert is_avenoril_continuation_allowed(patient) is False


def test_continuation_marker_v_90_is_denied():
    patient = {
        "avenoril_allergy": False,
        "marker_v": 90,
        "followup_current": True,
    }
    assert is_avenoril_continuation_allowed(patient) is False
