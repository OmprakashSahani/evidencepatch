from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evidencepatch.baseline_prompt import BASELINE_PROMPT


def test_baseline_prompt_is_nonempty_string():
    assert isinstance(BASELINE_PROMPT, str)
    assert BASELINE_PROMPT.strip()


def test_baseline_prompt_contains_required_contract_terms():
    for term in (
        "PATCH",
        "NO_PATCH",
        "ESCALATE",
        "evidencepatch_result.json",
        "changed_files",
        "evidence_ids",
        "human_review_required",
    ):
        assert term in BASELINE_PROMPT


def test_baseline_prompt_prohibits_private_and_external_sources():
    lowered = BASELINE_PROMPT.lower()
    assert "hidden tests" in lowered
    assert "ground truth" in lowered
    assert "internet, web search" in lowered
    assert "parent directories or paths outside this workspace" in lowered


def test_baseline_prompt_omits_advanced_mechanism_names():
    for term in (
        "Clinical Change Contract",
        "authority gate",
        "provenance verifier",
        "VUSR",
    ):
        assert term not in BASELINE_PROMPT
