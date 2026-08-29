import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.hidden_target import resolve_hidden_target_repo


CASE_REPOSITORY = resolve_hidden_target_repo(__file__)
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.velunex import is_velunex_allowed


def test_existing_allergy_behavior_is_preserved():
    patient = {"velunex_allergy": True, "marker_q": 69}

    assert is_velunex_allowed(patient) is False


def test_marker_q_69_is_allowed_without_allergy():
    patient = {"velunex_allergy": False, "marker_q": 69}

    assert is_velunex_allowed(patient) is True


def test_marker_q_70_is_denied_without_allergy():
    patient = {"velunex_allergy": False, "marker_q": 70}

    assert is_velunex_allowed(patient) is False


def test_marker_q_71_is_denied_without_allergy():
    patient = {"velunex_allergy": False, "marker_q": 71}

    assert is_velunex_allowed(patient) is False
