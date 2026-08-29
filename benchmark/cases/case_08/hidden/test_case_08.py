import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.hidden_target import resolve_hidden_target_repo


CASE_REPOSITORY = resolve_hidden_target_repo(__file__)
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.dorevex import is_dorevex_allowed


def test_primary_pathway_remains_allowed():
    patient = {
        "dorevex_allergy": False,
        "treatment_path": "primary",
        "marker_u": 0,
        "specialist_approved": False,
    }

    assert is_dorevex_allowed(patient) is True


def test_allergy_contraindication_is_preserved():
    patient = {
        "dorevex_allergy": True,
        "treatment_path": "primary",
        "marker_u": 100,
        "specialist_approved": True,
    }

    assert is_dorevex_allowed(patient) is False


def test_adjunct_at_old_threshold_is_denied():
    patient = {
        "dorevex_allergy": False,
        "treatment_path": "adjunct",
        "marker_u": 30,
        "specialist_approved": True,
    }

    assert is_dorevex_allowed(patient) is False


def test_adjunct_above_old_threshold_is_denied():
    patient = {
        "dorevex_allergy": False,
        "treatment_path": "adjunct",
        "marker_u": 100,
        "specialist_approved": True,
    }

    assert is_dorevex_allowed(patient) is False


def test_adjunct_below_old_threshold_remains_denied():
    patient = {
        "dorevex_allergy": False,
        "treatment_path": "adjunct",
        "marker_u": 29,
        "specialist_approved": True,
    }

    assert is_dorevex_allowed(patient) is False


def test_adjunct_without_specialist_approval_remains_denied():
    patient = {
        "dorevex_allergy": False,
        "treatment_path": "adjunct",
        "marker_u": 50,
        "specialist_approved": False,
    }

    assert is_dorevex_allowed(patient) is False


def test_unknown_pathway_remains_denied():
    patient = {
        "dorevex_allergy": False,
        "treatment_path": "unknown",
        "marker_u": 100,
        "specialist_approved": True,
    }

    assert is_dorevex_allowed(patient) is False
