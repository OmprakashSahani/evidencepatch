import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.continuation import is_avenoril_continuation_allowed


def test_allergy_denies_continuation():
    patient = {
        "avenoril_allergy": True,
        "followup_current": True,
    }

    assert is_avenoril_continuation_allowed(patient) is False


def test_outdated_followup_denies_continuation():
    patient = {
        "avenoril_allergy": False,
        "followup_current": False,
    }

    assert is_avenoril_continuation_allowed(patient) is False


def test_current_followup_allows_continuation_regardless_of_marker_v():
    patient = {
        "avenoril_allergy": False,
        "followup_current": True,
        "marker_v": 90,
    }

    assert is_avenoril_continuation_allowed(patient) is True
