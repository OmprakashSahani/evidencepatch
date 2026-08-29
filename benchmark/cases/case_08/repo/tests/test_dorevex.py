import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.dorevex import is_dorevex_allowed


def test_primary_pathway_is_allowed_without_allergy():
    patient = {"dorevex_allergy": False, "treatment_path": "primary"}

    assert is_dorevex_allowed(patient) is True


def test_primary_pathway_is_denied_with_allergy():
    patient = {"dorevex_allergy": True, "treatment_path": "primary"}

    assert is_dorevex_allowed(patient) is False


def test_qualified_adjunct_pathway_is_allowed():
    patient = {
        "dorevex_allergy": False,
        "treatment_path": "adjunct",
        "marker_u": 30,
        "specialist_approved": True,
    }

    assert is_dorevex_allowed(patient) is True


def test_adjunct_below_marker_threshold_is_denied():
    patient = {
        "dorevex_allergy": False,
        "treatment_path": "adjunct",
        "marker_u": 29,
        "specialist_approved": True,
    }

    assert is_dorevex_allowed(patient) is False


def test_adjunct_without_specialist_approval_is_denied():
    patient = {
        "dorevex_allergy": False,
        "treatment_path": "adjunct",
        "marker_u": 50,
        "specialist_approved": False,
    }

    assert is_dorevex_allowed(patient) is False


def test_unknown_pathway_is_denied():
    patient = {"dorevex_allergy": False, "treatment_path": "unknown"}

    assert is_dorevex_allowed(patient) is False
