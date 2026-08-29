import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.hidden_target import resolve_hidden_target_repo


CASE_REPOSITORY = resolve_hidden_target_repo(__file__)
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.virelune import is_virelune_allowed


def test_allergy_takes_precedence_over_valid_exception():
    patient = {
        "virelune_allergy": True,
        "marker_t": 90,
        "exception_approved": True,
        "monitoring_current": True,
    }

    assert is_virelune_allowed(patient) is False


def test_marker_t_79_preserves_existing_eligibility():
    patient = {
        "virelune_allergy": False,
        "marker_t": 79,
        "exception_approved": False,
        "monitoring_current": False,
    }

    assert is_virelune_allowed(patient) is True


def test_marker_t_80_without_approval_is_denied():
    patient = {
        "virelune_allergy": False,
        "marker_t": 80,
        "exception_approved": False,
        "monitoring_current": True,
    }

    assert is_virelune_allowed(patient) is False


def test_marker_t_80_without_current_monitoring_is_denied():
    patient = {
        "virelune_allergy": False,
        "marker_t": 80,
        "exception_approved": True,
        "monitoring_current": False,
    }

    assert is_virelune_allowed(patient) is False


def test_marker_t_80_with_valid_exception_is_allowed():
    patient = {
        "virelune_allergy": False,
        "marker_t": 80,
        "exception_approved": True,
        "monitoring_current": True,
    }

    assert is_virelune_allowed(patient) is True


def test_marker_t_100_with_valid_exception_is_allowed():
    patient = {
        "virelune_allergy": False,
        "marker_t": 100,
        "exception_approved": True,
        "monitoring_current": True,
    }

    assert is_virelune_allowed(patient) is True


def test_marker_t_100_without_exception_is_denied():
    patient = {
        "virelune_allergy": False,
        "marker_t": 100,
        "exception_approved": False,
        "monitoring_current": False,
    }

    assert is_virelune_allowed(patient) is False
