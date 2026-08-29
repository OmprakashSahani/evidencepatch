import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.velunex import is_velunex_allowed


def test_velunex_allergy_is_denied():
    patient = {"velunex_allergy": True}

    assert is_velunex_allowed(patient) is False


def test_no_velunex_allergy_is_allowed():
    patient = {"velunex_allergy": False}

    assert is_velunex_allowed(patient) is True
