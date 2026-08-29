import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.hidden_target import resolve_hidden_target_repo


CASE_REPOSITORY = resolve_hidden_target_repo(__file__)
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.merovant import is_merovant_allowed


def test_allergy_contraindication_is_preserved():
    patient = {"merovant_allergy": True, "marker_x": 69}

    assert is_merovant_allowed(patient) is False


def test_marker_x_59_is_allowed_without_allergy():
    patient = {"merovant_allergy": False, "marker_x": 59}

    assert is_merovant_allowed(patient) is True


def test_marker_x_60_is_allowed_without_allergy():
    patient = {"merovant_allergy": False, "marker_x": 60}

    assert is_merovant_allowed(patient) is True


def test_marker_x_64_is_allowed_without_allergy():
    patient = {"merovant_allergy": False, "marker_x": 64}

    assert is_merovant_allowed(patient) is True


def test_marker_x_65_is_allowed_without_allergy():
    patient = {"merovant_allergy": False, "marker_x": 65}

    assert is_merovant_allowed(patient) is True


def test_marker_x_69_is_allowed_without_allergy():
    patient = {"merovant_allergy": False, "marker_x": 69}

    assert is_merovant_allowed(patient) is True


def test_marker_x_70_is_denied_without_allergy():
    patient = {"merovant_allergy": False, "marker_x": 70}

    assert is_merovant_allowed(patient) is False


def test_marker_x_90_is_denied_without_allergy():
    patient = {"merovant_allergy": False, "marker_x": 90}

    assert is_merovant_allowed(patient) is False
