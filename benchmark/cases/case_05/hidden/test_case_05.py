import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.hidden_target import resolve_hidden_target_repo


CASE_REPOSITORY = resolve_hidden_target_repo(__file__)
sys.path.insert(0, str(CASE_REPOSITORY))

from medication_rules.lumetra import is_lumetra_allowed


def test_adult_is_allowed_without_allergy():
    assert is_lumetra_allowed(
        {"lumetra_allergy": False, "age_group": "adult"}
    ) is True


def test_adolescent_is_allowed_without_allergy():
    assert is_lumetra_allowed(
        {"lumetra_allergy": False, "age_group": "adolescent"}
    ) is True


def test_child_remains_ineligible():
    assert is_lumetra_allowed(
        {"lumetra_allergy": False, "age_group": "child"}
    ) is False


def test_adult_allergy_contraindication_is_preserved():
    assert is_lumetra_allowed(
        {"lumetra_allergy": True, "age_group": "adult"}
    ) is False


def test_adolescent_with_allergy_is_denied():
    assert is_lumetra_allowed(
        {"lumetra_allergy": True, "age_group": "adolescent"}
    ) is False
