import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1] / "repo"
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.teralune import is_teralune_allowed


def test_existing_allergy_contraindication_is_preserved():
    patient = {"teralune_allergy": True, "marker_r": 49}

    assert is_teralune_allowed(patient) is False


def test_marker_r_49_is_allowed_without_allergy():
    patient = {"teralune_allergy": False, "marker_r": 49}

    assert is_teralune_allowed(patient) is True


def test_marker_r_50_is_allowed_without_allergy():
    patient = {"teralune_allergy": False, "marker_r": 50}

    assert is_teralune_allowed(patient) is True


def test_marker_r_80_is_allowed_without_allergy():
    patient = {"teralune_allergy": False, "marker_r": 80}

    assert is_teralune_allowed(patient) is True
