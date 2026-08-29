import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1] / "repo"
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.serevon import is_serevon_allowed


def test_allergy_is_denied_with_current_monitoring():
    patient = {"serevon_allergy": True, "monitoring_current": True}

    assert is_serevon_allowed(patient) is False


def test_allergy_is_denied_without_current_monitoring():
    patient = {"serevon_allergy": True, "monitoring_current": False}

    assert is_serevon_allowed(patient) is False


def test_no_allergy_with_current_monitoring_is_allowed():
    patient = {"serevon_allergy": False, "monitoring_current": True}

    assert is_serevon_allowed(patient) is True


def test_no_allergy_without_current_monitoring_is_denied():
    patient = {"serevon_allergy": False, "monitoring_current": False}

    assert is_serevon_allowed(patient) is False
