import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.hidden_target import resolve_hidden_target_repo


CASE_REPOSITORY = resolve_hidden_target_repo(__file__)
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.zoravel import is_zoravel_allowed


def test_allergy_contraindication_is_preserved():
    patient = {"zoravel_allergy": True, "marker_w": 74}

    assert is_zoravel_allowed(patient) is False


def test_marker_w_74_is_allowed_without_allergy():
    patient = {"zoravel_allergy": False, "marker_w": 74}

    assert is_zoravel_allowed(patient) is True


def test_marker_w_75_is_denied_without_allergy():
    patient = {"zoravel_allergy": False, "marker_w": 75}

    assert is_zoravel_allowed(patient) is False


def test_marker_w_80_is_denied_without_allergy():
    patient = {"zoravel_allergy": False, "marker_w": 80}

    assert is_zoravel_allowed(patient) is False


def test_marker_w_85_is_denied_without_allergy():
    patient = {"zoravel_allergy": False, "marker_w": 85}

    assert is_zoravel_allowed(patient) is False


def test_marker_w_100_is_denied_without_allergy():
    patient = {"zoravel_allergy": False, "marker_w": 100}

    assert is_zoravel_allowed(patient) is False
