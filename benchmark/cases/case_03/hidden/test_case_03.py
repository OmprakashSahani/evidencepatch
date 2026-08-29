import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.hidden_target import resolve_hidden_target_repo


CASE_REPOSITORY = resolve_hidden_target_repo(__file__)
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.norvexa import is_norvexa_high_dose_allowed


def test_existing_allergy_contraindication_is_preserved():
    assert is_norvexa_high_dose_allowed(
        {"norvexa_allergy": True, "clearance_z": 60}
    ) is False


def test_clearance_z_39_is_denied():
    assert is_norvexa_high_dose_allowed(
        {"norvexa_allergy": False, "clearance_z": 39}
    ) is False


def test_clearance_z_40_is_denied():
    assert is_norvexa_high_dose_allowed(
        {"norvexa_allergy": False, "clearance_z": 40}
    ) is False


def test_clearance_z_54_is_denied():
    assert is_norvexa_high_dose_allowed(
        {"norvexa_allergy": False, "clearance_z": 54}
    ) is False


def test_clearance_z_55_is_allowed():
    assert is_norvexa_high_dose_allowed(
        {"norvexa_allergy": False, "clearance_z": 55}
    ) is True


def test_clearance_z_60_is_allowed():
    assert is_norvexa_high_dose_allowed(
        {"norvexa_allergy": False, "clearance_z": 60}
    ) is True
