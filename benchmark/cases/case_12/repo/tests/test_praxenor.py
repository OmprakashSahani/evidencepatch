import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.praxenor import is_praxenor_allowed


def test_allergy_is_denied():
    patient = {"praxenor_allergy": True, "marker_y": 20}

    assert is_praxenor_allowed(patient) is False


def test_marker_y_49_is_allowed_without_allergy():
    patient = {"praxenor_allergy": False, "marker_y": 49}

    assert is_praxenor_allowed(patient) is True


def test_marker_y_50_is_denied_without_allergy():
    patient = {"praxenor_allergy": False, "marker_y": 50}

    assert is_praxenor_allowed(patient) is False


def test_marker_y_80_is_denied_without_allergy():
    patient = {"praxenor_allergy": False, "marker_y": 80}

    assert is_praxenor_allowed(patient) is False
