import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from evidencepatch.change_contract import (
    ClinicalChangeContract,
    EvidenceAssessment,
    EvidenceAuthority,
    EvidenceStatus,
)
from evidencepatch.contract_extraction import (
    CONTRACT_EXTRACTION_PROMPT,
    CONTRACT_FILENAME,
    contract_from_json,
    contract_from_mapping,
    contract_to_json,
    contract_to_mapping,
    load_contract,
)


def valid_mapping() -> dict[str, object]:
    return {
        "schema_version": 1,
        "evidence": [
            {
                "evidence_id": "SYNTHETIC-SOURCE-A",
                "authority": "AUTHORITATIVE",
                "status": "CURRENT",
                "proposes_executable_change": True,
                "conflicts_with_current_authority": False,
            }
        ],
        "executable_behavior_change": True,
        "semantic_equivalence": False,
        "unresolved_conflict": False,
        "ambiguous_or_incomplete": False,
        "rationale": "The current source establishes a behavioral delta.",
    }


def test_valid_mapping_parses_to_immutable_contract() -> None:
    contract = contract_from_mapping(valid_mapping())
    assert isinstance(contract, ClinicalChangeContract)
    assert contract.evidence[0].authority is EvidenceAuthority.AUTHORITATIVE
    with pytest.raises(FrozenInstanceError):
        contract.rationale = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("authority", [item.value for item in EvidenceAuthority])
def test_every_authority_parses(authority: str) -> None:
    data = valid_mapping()
    data["evidence"][0]["authority"] = authority  # type: ignore[index]
    assert contract_from_mapping(data).evidence[0].authority.value == authority


@pytest.mark.parametrize("status", [item.value for item in EvidenceStatus])
def test_every_status_parses(status: str) -> None:
    data = valid_mapping()
    data["evidence"][0]["status"] = status  # type: ignore[index]
    assert contract_from_mapping(data).evidence[0].status.value == status


def test_missing_top_level_field_rejected() -> None:
    data = valid_mapping()
    del data["rationale"]
    with pytest.raises(ValueError, match="missing.*rationale"):
        contract_from_mapping(data)


def test_extra_top_level_field_rejected() -> None:
    data = valid_mapping()
    data["extra"] = True
    with pytest.raises(ValueError, match="extra"):
        contract_from_mapping(data)


def test_missing_evidence_field_rejected() -> None:
    data = valid_mapping()
    del data["evidence"][0]["status"]  # type: ignore[index]
    with pytest.raises(ValueError, match="missing.*status"):
        contract_from_mapping(data)


def test_extra_evidence_field_rejected() -> None:
    data = valid_mapping()
    data["evidence"][0]["extra"] = True  # type: ignore[index]
    with pytest.raises(ValueError, match="extra"):
        contract_from_mapping(data)


@pytest.mark.parametrize("field,value", [("authority", "OTHER"), ("status", "RETIRED")])
def test_invalid_enum_string_rejected(field: str, value: str) -> None:
    data = valid_mapping()
    data["evidence"][0][field] = value  # type: ignore[index]
    with pytest.raises(ValueError, match=field):
        contract_from_mapping(data)


@pytest.mark.parametrize("field,value", [("authority", "authoritative"), ("status", "current")])
def test_lowercase_enum_alias_rejected(field: str, value: str) -> None:
    data = valid_mapping()
    data["evidence"][0][field] = value  # type: ignore[index]
    with pytest.raises(ValueError, match=field):
        contract_from_mapping(data)


@pytest.mark.parametrize("field,value", [("authority", " AUTHORITATIVE"), ("status", "CURRENT ")])
def test_whitespace_padded_enum_rejected(field: str, value: str) -> None:
    data = valid_mapping()
    data["evidence"][0][field] = value  # type: ignore[index]
    with pytest.raises(ValueError, match=field):
        contract_from_mapping(data)


@pytest.mark.parametrize("value", [1, True, None])
@pytest.mark.parametrize("field", ["authority", "status"])
def test_non_string_enum_rejected(field: str, value: object) -> None:
    data = valid_mapping()
    data["evidence"][0][field] = value  # type: ignore[index]
    with pytest.raises(ValueError, match=field):
        contract_from_mapping(data)


@pytest.mark.parametrize("value", [None, {}, "source"])
def test_non_list_evidence_rejected(value: object) -> None:
    data = valid_mapping()
    data["evidence"] = value
    with pytest.raises(ValueError, match="evidence"):
        contract_from_mapping(data)


def test_empty_evidence_rejected() -> None:
    data = valid_mapping()
    data["evidence"] = []
    with pytest.raises(ValueError, match="non-empty"):
        contract_from_mapping(data)


def test_non_object_evidence_item_rejected() -> None:
    data = valid_mapping()
    data["evidence"] = ["source"]
    with pytest.raises(ValueError, match="JSON object"):
        contract_from_mapping(data)


@pytest.mark.parametrize("field", ["proposes_executable_change", "conflicts_with_current_authority"])
@pytest.mark.parametrize("value", [0, 1, "true", None])
def test_non_bool_assessment_value_rejected(field: str, value: object) -> None:
    data = valid_mapping()
    data["evidence"][0][field] = value  # type: ignore[index]
    with pytest.raises(ValueError, match=field):
        contract_from_mapping(data)


@pytest.mark.parametrize("field", ["executable_behavior_change", "semantic_equivalence", "unresolved_conflict", "ambiguous_or_incomplete"])
@pytest.mark.parametrize("value", [0, 1, "false", None])
def test_non_bool_contract_value_rejected(field: str, value: object) -> None:
    data = valid_mapping()
    data[field] = value
    with pytest.raises(ValueError, match=field):
        contract_from_mapping(data)


@pytest.mark.parametrize("value", [0, 2, True, "1", None])
def test_invalid_schema_version_rejected(value: object) -> None:
    data = valid_mapping()
    data["schema_version"] = value
    with pytest.raises(ValueError, match="schema_version"):
        contract_from_mapping(data)


def test_invalid_json_rejected() -> None:
    with pytest.raises(ValueError, match="invalid contract JSON"):
        contract_from_json('{"schema_version": 1} trailing')


def test_blank_json_rejected() -> None:
    with pytest.raises(ValueError, match="blank"):
        contract_from_json("  \n")


def test_non_string_json_rejected() -> None:
    with pytest.raises(ValueError, match="string"):
        contract_from_json(None)  # type: ignore[arg-type]


def test_valid_file_loads(tmp_path: Path) -> None:
    path = tmp_path / CONTRACT_FILENAME
    path.write_text(json.dumps(valid_mapping()), encoding="utf-8")
    assert load_contract(path) == contract_from_mapping(valid_mapping())


def test_missing_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        load_contract(tmp_path / CONTRACT_FILENAME)


def test_directory_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="regular file"):
        load_contract(tmp_path)


def test_symlink_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text(json.dumps(valid_mapping()), encoding="utf-8")
    link = tmp_path / CONTRACT_FILENAME
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symbolic link"):
        load_contract(link)


def test_invalid_utf8_rejected(tmp_path: Path) -> None:
    path = tmp_path / CONTRACT_FILENAME
    path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="UTF-8"):
        load_contract(path)


def test_contract_to_mapping_has_exact_shape() -> None:
    mapping = valid_mapping()
    assert contract_to_mapping(contract_from_mapping(mapping)) == mapping


def test_contract_to_mapping_rejects_wrong_type() -> None:
    with pytest.raises(ValueError, match="ClinicalChangeContract"):
        contract_to_mapping({})  # type: ignore[arg-type]


def test_contract_to_json_is_deterministic() -> None:
    expected = json.dumps(valid_mapping(), indent=2, sort_keys=True) + "\n"
    assert contract_to_json(contract_from_mapping(valid_mapping())) == expected


def test_json_round_trip_preserves_equality() -> None:
    contract = contract_from_mapping(valid_mapping())
    assert contract_from_json(contract_to_json(contract)) == contract


def test_evidence_order_preserved() -> None:
    data = valid_mapping()
    second = dict(data["evidence"][0])  # type: ignore[index]
    second["evidence_id"] = "SYNTHETIC-SOURCE-B"
    data["evidence"].append(second)  # type: ignore[union-attr]
    contract = contract_from_mapping(data)
    assert [item["evidence_id"] for item in contract_to_mapping(contract)["evidence"]] == ["SYNTHETIC-SOURCE-A", "SYNTHETIC-SOURCE-B"]  # type: ignore[index]


def test_whitespace_evidence_id_rejected_through_parser() -> None:
    data = valid_mapping()
    data["evidence"][0]["evidence_id"] = " SYNTHETIC-SOURCE-A "  # type: ignore[index]
    with pytest.raises(ValueError, match="stripped"):
        contract_from_mapping(data)


def test_whitespace_rationale_rejected_through_parser() -> None:
    data = valid_mapping()
    data["rationale"] = " rationale "
    with pytest.raises(ValueError, match="stripped"):
        contract_from_mapping(data)


def test_duplicate_evidence_ids_rejected_through_parser() -> None:
    data = valid_mapping()
    data["evidence"].append(dict(data["evidence"][0]))  # type: ignore[union-attr,index]
    with pytest.raises(ValueError, match="unique"):
        contract_from_mapping(data)


def test_contradictory_semantics_rejected() -> None:
    data = valid_mapping()
    data["semantic_equivalence"] = True
    with pytest.raises(ValueError, match="cannot both be true"):
        contract_from_mapping(data)


def test_prompt_contains_all_enum_values() -> None:
    for item in (*EvidenceAuthority, *EvidenceStatus):
        assert item.value in CONTRACT_EXTRACTION_PROMPT


def test_prompt_names_contract_artifact() -> None:
    assert CONTRACT_FILENAME in CONTRACT_EXTRACTION_PROMPT


def test_prompt_forbids_final_action_selection() -> None:
    assert "not final action selection" in CONTRACT_EXTRACTION_PROMPT
    assert "Do not select or output PATCH, NO_PATCH,\nor ESCALATE" in CONTRACT_EXTRACTION_PROMPT


def test_prompt_forbids_repo_modification() -> None:
    assert "Do not modify anything under repo/" in CONTRACT_EXTRACTION_PROMPT


def test_prompt_forbids_internet_and_search() -> None:
    assert "Do not use the internet, web search, or\nexternal search" in CONTRACT_EXTRACTION_PROMPT


def test_prompt_omits_private_benchmark_terms() -> None:
    lowered = CONTRACT_EXTRACTION_PROMPT.lower()
    assert "ground_truth.json" not in lowered
    assert "hidden tests" not in lowered
