import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.teralune import is_teralune_allowed


def test_teralune_allergy_is_denied():
    patient = {"teralune_allergy": True, "marker_r": 49}

    assert is_teralune_allowed(patient) is False


def test_marker_r_at_threshold_is_denied_without_allergy():
    patient = {"teralune_allergy": False, "marker_r": 50}

    assert is_teralune_allowed(patient) is False


def test_marker_r_below_threshold_is_allowed_without_allergy():
    patient = {"teralune_allergy": False, "marker_r": 49}

    assert is_teralune_allowed(patient) is True
