import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.virelune import is_virelune_allowed


def test_virelune_allergy_is_denied():
    patient = {"virelune_allergy": True, "marker_t": 79}

    assert is_virelune_allowed(patient) is False


def test_marker_t_79_is_allowed_without_allergy():
    patient = {"virelune_allergy": False, "marker_t": 79}

    assert is_virelune_allowed(patient) is True


def test_marker_t_80_is_denied_without_allergy():
    patient = {"virelune_allergy": False, "marker_t": 80}

    assert is_virelune_allowed(patient) is False


def test_marker_t_100_is_denied_without_allergy():
    patient = {"virelune_allergy": False, "marker_t": 100}

    assert is_virelune_allowed(patient) is False
