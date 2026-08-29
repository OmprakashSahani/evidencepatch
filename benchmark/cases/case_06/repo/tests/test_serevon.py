import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.serevon import is_serevon_allowed


def test_serevon_allergy_is_denied():
    patient = {"serevon_allergy": True}

    assert is_serevon_allowed(patient) is False


def test_no_serevon_allergy_is_allowed():
    patient = {"serevon_allergy": False}

    assert is_serevon_allowed(patient) is True
