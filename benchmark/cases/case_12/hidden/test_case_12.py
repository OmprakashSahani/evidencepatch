import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.hidden_target import resolve_hidden_target_repo


CASE_REPOSITORY = resolve_hidden_target_repo(__file__)
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.praxenor import is_praxenor_allowed


def test_allergy_is_denied_at_marker_y_0():
    patient = {"praxenor_allergy": True, "marker_y": 0}

    assert is_praxenor_allowed(patient) is False


def test_allergy_is_denied_at_marker_y_49():
    patient = {"praxenor_allergy": True, "marker_y": 49}

    assert is_praxenor_allowed(patient) is False


def test_marker_y_0_is_allowed_without_allergy():
    patient = {"praxenor_allergy": False, "marker_y": 0}

    assert is_praxenor_allowed(patient) is True


def test_marker_y_49_is_allowed_without_allergy():
    patient = {"praxenor_allergy": False, "marker_y": 49}

    assert is_praxenor_allowed(patient) is True


def test_marker_y_50_is_denied_without_allergy():
    patient = {"praxenor_allergy": False, "marker_y": 50}

    assert is_praxenor_allowed(patient) is False


def test_marker_y_51_is_denied_without_allergy():
    patient = {"praxenor_allergy": False, "marker_y": 51}

    assert is_praxenor_allowed(patient) is False


def test_marker_y_100_is_denied_without_allergy():
    patient = {"praxenor_allergy": False, "marker_y": 100}

    assert is_praxenor_allowed(patient) is False
