import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.zoravel import is_zoravel_allowed


def test_allergy_is_denied():
    patient = {"zoravel_allergy": True, "marker_w": 50}

    assert is_zoravel_allowed(patient) is False


def test_marker_w_74_is_allowed_without_allergy():
    patient = {"zoravel_allergy": False, "marker_w": 74}

    assert is_zoravel_allowed(patient) is True


def test_marker_w_75_is_denied_without_allergy():
    patient = {"zoravel_allergy": False, "marker_w": 75}

    assert is_zoravel_allowed(patient) is False


def test_marker_w_90_is_denied_without_allergy():
    patient = {"zoravel_allergy": False, "marker_w": 90}

    assert is_zoravel_allowed(patient) is False
