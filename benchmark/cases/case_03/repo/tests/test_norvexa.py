import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.norvexa import is_norvexa_high_dose_allowed


def test_norvexa_allergy_is_denied():
    assert is_norvexa_high_dose_allowed(
        {"norvexa_allergy": True, "clearance_z": 60}
    ) is False


def test_clearance_z_39_is_denied_without_allergy():
    assert is_norvexa_high_dose_allowed(
        {"norvexa_allergy": False, "clearance_z": 39}
    ) is False


def test_clearance_z_40_is_allowed_without_allergy():
    assert is_norvexa_high_dose_allowed(
        {"norvexa_allergy": False, "clearance_z": 40}
    ) is True


def test_clearance_z_60_is_allowed_without_allergy():
    assert is_norvexa_high_dose_allowed(
        {"norvexa_allergy": False, "clearance_z": 60}
    ) is True
