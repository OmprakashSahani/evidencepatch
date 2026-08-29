import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.merovant import is_merovant_allowed


def test_allergy_is_denied():
    patient = {"merovant_allergy": True, "marker_x": 50}

    assert is_merovant_allowed(patient) is False


def test_marker_x_69_is_allowed_without_allergy():
    patient = {"merovant_allergy": False, "marker_x": 69}

    assert is_merovant_allowed(patient) is True


def test_marker_x_70_is_denied_without_allergy():
    patient = {"merovant_allergy": False, "marker_x": 70}

    assert is_merovant_allowed(patient) is False


def test_marker_x_90_is_denied_without_allergy():
    patient = {"merovant_allergy": False, "marker_x": 90}

    assert is_merovant_allowed(patient) is False
