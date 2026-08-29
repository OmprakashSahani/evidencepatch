"""Strict serialization boundary for extracted clinical change contracts."""

import json
from json import JSONDecodeError
from pathlib import Path

from evidencepatch.change_contract import (
    ClinicalChangeContract,
    EvidenceAssessment,
    EvidenceAuthority,
    EvidenceStatus,
)


CONTRACT_FILENAME = "evidencepatch_contract.json"
CONTRACT_SCHEMA_VERSION = 1

CONTRACT_EXTRACTION_PROMPT = """You are an evidence-assessment agent for a clinical-software maintenance task.

Work only with the public inputs in the supplied workspace:
- task.md
- evidence/
- repo/

Do not access files outside the supplied workspace, hidden evaluation data,
evaluator code, or benchmark answers. Do not use the internet, web search, or
external search. Do not modify anything under repo/. Do not create
evidencepatch_result.json. Your only output artifact must be
evidencepatch_contract.json at the workspace root.

Your job is evidence assessment, not final action selection. Inspect the
maintenance task, every supplied evidence file, the current repository
implementation, and visible repository tests when relevant. Produce a
structured Clinical Change Contract. Do not select or output PATCH, NO_PATCH,
or ESCALATE.

Represent every supplied evidence document exactly once. For each document,
copy its evidence or document ID exactly. If no ID can be identified, use a
clearly synthetic local identifier formed from its relative evidence filename
with the prefix UNRESOLVED:, such as UNRESOLVED:guidance.txt. Never invent an
authoritative-looking ID.

For each evidence item, provide:
- evidence_id
- authority: exactly AUTHORITATIVE, NON_AUTHORITATIVE, DRAFT, or UNKNOWN
- status: exactly CURRENT, SUPERSEDED, PROVISIONAL, or UNKNOWN
- proposes_executable_change
- conflicts_with_current_authority

Classify authority and status from the supplied evidence itself. When either
is unclear, use UNKNOWN. Do not infer authority merely from recency, filename,
confident wording, or publication date.

proposes_executable_change is specific to one evidence item. Set it to true
when that item proposes executable behavior different from the current
repository behavior, even if the item is non-authoritative, draft, or
provisional. It describes change pressure, not permission to modify software.
Set it to false when the item restates current behavior, is semantically
equivalent, is contextual only, or contains no executable recommendation.

Set conflicts_with_current_authority to true when the item proposes executable
behavior incompatible with controlling CURRENT AUTHORITATIVE evidence. Do not
mark an item conflicting merely because it is older or superseded. If no
current authoritative evidence can be identified for comparison, do not
invent a conflict; represent the uncertainty through authority, status, and
contract-level ambiguity.

executable_behavior_change is contract-level. Set it to true only when there
is a genuine executable difference between the current repository and the
resolved controlling current authoritative evidence. A non-authoritative or
draft item can propose a change while executable_behavior_change remains false
because no controlling authoritative change has been established.

Set semantic_equivalence to true only when the relevant resolved current
authoritative evidence and current executable repository behavior are
behaviorally equivalent despite differences in wording, structure, polarity,
or terminology. Examples include positive eligibility wording versus an
equivalent contraindication, a logically equivalent threshold expression, or
documentation restructuring without behavioral change. Do not use this field
merely because a code modification seems undesirable.

Set unresolved_conflict to true when the supplied evidence contains a conflict
that remains unresolved for determining the controlling executable
requirement. A weaker source disagreeing with clearly controlling current
authoritative evidence does not necessarily make that requirement unresolved;
represent the weaker item through its authority and
conflicts_with_current_authority fields.

Set ambiguous_or_incomplete to true when the evidence does not provide one
sufficiently clear, complete, resolved basis for executable behavior. Examples
include unresolved candidate values, tentative language without a finalized
directive, missing controlling authority for a proposed change, or incomplete
conditions needed for safe implementation. Use it for genuine ambiguity or
incompleteness, not general caution.

Provide a concise, source-grounded rationale describing what evidence
controls, whether a genuine authoritative executable delta exists, and any
conflict, uncertainty, or semantic equivalence. Do not include a final action
label.

Write exactly one JSON object with this shape:
{
  "schema_version": 1,
  "evidence": [
    {
      "evidence_id": "...",
      "authority": "AUTHORITATIVE|NON_AUTHORITATIVE|DRAFT|UNKNOWN",
      "status": "CURRENT|SUPERSEDED|PROVISIONAL|UNKNOWN",
      "proposes_executable_change": true,
      "conflicts_with_current_authority": false
    }
  ],
  "executable_behavior_change": true,
  "semantic_equivalence": false,
  "unresolved_conflict": false,
  "ambiguous_or_incomplete": false,
  "rationale": "..."
}

Do not add top-level or evidence-item fields. Do not use Markdown fences or
comments. Represent structural uncertainty with UNKNOWN and the ambiguity
fields rather than inventing facts.
"""


_CONTRACT_FIELDS = {
    "schema_version",
    "evidence",
    "executable_behavior_change",
    "semantic_equivalence",
    "unresolved_conflict",
    "ambiguous_or_incomplete",
    "rationale",
}
_EVIDENCE_FIELDS = {
    "evidence_id",
    "authority",
    "status",
    "proposes_executable_change",
    "conflicts_with_current_authority",
}


def _require_exact_fields(data: dict[object, object], expected: set[str], context: str) -> None:
    actual = set(data)
    missing = sorted(expected - actual)
    extra = sorted(str(key) for key in actual - expected)
    if missing or extra:
        raise ValueError(f"{context} fields are invalid; missing={missing}, extra={extra}")


def _require_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _parse_enum(value: object, enum_type: type[EvidenceAuthority] | type[EvidenceStatus], field: str):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an exact string enum value")
    try:
        return enum_type(value)
    except ValueError as error:
        raise ValueError(f"{field} has invalid value {value!r}") from error


def contract_from_mapping(data: object) -> ClinicalChangeContract:
    """Build a contract from an exact schema-version-one JSON-style mapping."""
    if not isinstance(data, dict):
        raise ValueError("contract must be a JSON object")
    _require_exact_fields(data, _CONTRACT_FIELDS, "contract")

    schema_version = data["schema_version"]
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version != CONTRACT_SCHEMA_VERSION:
        raise ValueError("schema_version must be integer 1")

    evidence_data = data["evidence"]
    if not isinstance(evidence_data, list) or not evidence_data:
        raise ValueError("evidence must be a non-empty JSON list")

    evidence: list[EvidenceAssessment] = []
    for index, item in enumerate(evidence_data):
        if not isinstance(item, dict):
            raise ValueError(f"evidence[{index}] must be a JSON object")
        _require_exact_fields(item, _EVIDENCE_FIELDS, f"evidence[{index}]")
        evidence.append(
            EvidenceAssessment(
                evidence_id=item["evidence_id"],
                authority=_parse_enum(item["authority"], EvidenceAuthority, f"evidence[{index}].authority"),
                status=_parse_enum(item["status"], EvidenceStatus, f"evidence[{index}].status"),
                proposes_executable_change=_require_bool(item["proposes_executable_change"], f"evidence[{index}].proposes_executable_change"),
                conflicts_with_current_authority=_require_bool(item["conflicts_with_current_authority"], f"evidence[{index}].conflicts_with_current_authority"),
            )
        )

    return ClinicalChangeContract(
        schema_version=schema_version,
        evidence=tuple(evidence),
        executable_behavior_change=_require_bool(data["executable_behavior_change"], "executable_behavior_change"),
        semantic_equivalence=_require_bool(data["semantic_equivalence"], "semantic_equivalence"),
        unresolved_conflict=_require_bool(data["unresolved_conflict"], "unresolved_conflict"),
        ambiguous_or_incomplete=_require_bool(data["ambiguous_or_incomplete"], "ambiguous_or_incomplete"),
        rationale=data["rationale"],
    )


def contract_from_json(text: str) -> ClinicalChangeContract:
    """Parse strict JSON text into a validated clinical change contract."""
    if not isinstance(text, str):
        raise ValueError("contract JSON text must be a string")
    if not text.strip():
        raise ValueError("contract JSON text must not be blank")
    try:
        data = json.loads(text)
    except JSONDecodeError as error:
        raise ValueError(f"invalid contract JSON: {error.msg}") from error
    return contract_from_mapping(data)


def load_contract(path: Path) -> ClinicalChangeContract:
    """Load a UTF-8 contract artifact without following a result-file symlink."""
    if not isinstance(path, Path):
        raise ValueError("contract path must be a pathlib.Path")
    if path.is_symlink():
        raise ValueError("contract path must not be a symbolic link")
    if not path.exists():
        raise FileNotFoundError(f"contract file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"contract path is not a regular file: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"contract file is not valid UTF-8: {path}") from error
    return contract_from_json(text)


def contract_to_mapping(contract: ClinicalChangeContract) -> dict[str, object]:
    """Serialize a validated contract to exact JSON-compatible schema fields."""
    if not isinstance(contract, ClinicalChangeContract):
        raise ValueError("contract must be a ClinicalChangeContract")
    return {
        "schema_version": contract.schema_version,
        "evidence": [
            {
                "evidence_id": item.evidence_id,
                "authority": item.authority.value,
                "status": item.status.value,
                "proposes_executable_change": item.proposes_executable_change,
                "conflicts_with_current_authority": item.conflicts_with_current_authority,
            }
            for item in contract.evidence
        ],
        "executable_behavior_change": contract.executable_behavior_change,
        "semantic_equivalence": contract.semantic_equivalence,
        "unresolved_conflict": contract.unresolved_conflict,
        "ambiguous_or_incomplete": contract.ambiguous_or_incomplete,
        "rationale": contract.rationale,
    }


def contract_to_json(contract: ClinicalChangeContract) -> str:
    """Serialize a contract as deterministic, newline-terminated JSON."""
    return json.dumps(contract_to_mapping(contract), indent=2, sort_keys=True) + "\n"
