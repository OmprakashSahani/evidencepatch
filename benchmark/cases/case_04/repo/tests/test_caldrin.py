import sys
from pathlib import Path


CASE_REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.caldrin import is_caldrin_allowed


def test_adult_is_allowed_without_allergy():
    assert is_caldrin_allowed(
        {"caldrin_allergy": False, "age_group": "adult"}
    ) is True


def test_adolescent_is_allowed_without_allergy():
    assert is_caldrin_allowed(
        {"caldrin_allergy": False, "age_group": "adolescent"}
    ) is True


def test_child_is_denied_without_allergy():
    assert is_caldrin_allowed(
        {"caldrin_allergy": False, "age_group": "child"}
    ) is False


def test_caldrin_allergy_is_denied():
    assert is_caldrin_allowed(
        {"caldrin_allergy": True, "age_group": "adult"}
    ) is False
