import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.initiation import is_avenoril_initiation_allowed


def test_allergy_denies_initiation():
    patient = {
        "avenoril_allergy": True,
        "baseline_review_complete": True,
    }

    assert is_avenoril_initiation_allowed(patient) is False


def test_incomplete_baseline_review_denies_initiation():
    patient = {
        "avenoril_allergy": False,
        "baseline_review_complete": False,
    }

    assert is_avenoril_initiation_allowed(patient) is False


def test_complete_baseline_review_allows_initiation_regardless_of_marker_v():
    patient = {
        "avenoril_allergy": False,
        "baseline_review_complete": True,
        "marker_v": 90,
    }

    assert is_avenoril_initiation_allowed(patient) is True
