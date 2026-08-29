"""Deterministic MCP interface for EvidencePatch governance and verification."""

from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer
from pydantic import BaseModel, ConfigDict

from evidencepatch.change_contract import (
    ChangeAction,
    decide_change_action,
    requires_human_review,
)
from evidencepatch.contract_extraction import contract_from_mapping, contract_to_mapping
from evidencepatch.repo_diff import compare_repositories
from evidencepatch.result_contract import validate_solver_result


SERVER_INSTRUCTIONS = """EvidencePatch provides deterministic governance and verification for evidence-backed software maintenance. Use external providers such as Exa for evidence discovery before calling these tools; EvidencePatch operates only on structured evidence and local repository state. PATCH means the frozen governance gate found an authoritative executable delta. ESCALATE requires human review before software change. NO_PATCH authorizes no executable repository change. Software edits remain sandboxed and require human review before deployment. Outputs are software-maintenance evidence, not medical advice."""

mcp = MCPServer("EvidencePatch", instructions=SERVER_INSTRUCTIONS)


class EvidenceItemTransport(BaseModel):
    """MCP transport shape for one evidence assessment."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    authority: Literal["AUTHORITATIVE", "NON_AUTHORITATIVE", "DRAFT", "UNKNOWN"]
    status: Literal["CURRENT", "SUPERSEDED", "PROVISIONAL", "UNKNOWN"]
    proposes_executable_change: bool
    conflicts_with_current_authority: bool


class ContractTransport(BaseModel):
    """MCP transport shape for a proposed Clinical Change Contract."""

    model_config = ConfigDict(extra="forbid")

    evidence: list[EvidenceItemTransport]
    executable_behavior_change: bool
    semantic_equivalence: bool
    unresolved_conflict: bool
    ambiguous_or_incomplete: bool
    rationale: str


class ResultTransport(BaseModel):
    """MCP transport shape for a proposed EvidencePatch solver result."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    action: str
    changed_files: list[str]
    evidence_ids: list[str]
    human_review_required: bool
    summary: str


def _contract_mapping(value: ContractTransport) -> dict[str, object]:
    return {
        "schema_version": 1,
        "evidence": [item.model_dump(mode="python") for item in value.evidence],
        "executable_behavior_change": value.executable_behavior_change,
        "semantic_equivalence": value.semantic_equivalence,
        "unresolved_conflict": value.unresolved_conflict,
        "ambiguous_or_incomplete": value.ambiguous_or_incomplete,
        "rationale": value.rationale,
    }


def _repository_path(value: object, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty path string")
    path = Path(value)
    if path.is_symlink():
        raise ValueError(f"{field} must not be a symlink")
    if not path.exists():
        raise FileNotFoundError(f"{field} does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"{field} must be a directory")
    return path.resolve()


def _repository_pair(canonical_repo: object, candidate_repo: object) -> tuple[Path, Path]:
    canonical = _repository_path(canonical_repo, "canonical_repo")
    candidate = _repository_path(candidate_repo, "candidate_repo")
    if (
        canonical == candidate
        or canonical in candidate.parents
        or candidate in canonical.parents
    ):
        raise ValueError("canonical_repo and candidate_repo must be disjoint")
    return canonical, candidate


@mcp.tool(name="assess_change_contract", structured_output=True)
async def assess_change_contract(contract: ContractTransport) -> dict[str, Any]:
    """Validate structured evidence and apply deterministic change governance."""
    validated = contract_from_mapping(_contract_mapping(contract))
    action = decide_change_action(validated)
    review = requires_human_review(action)
    return {
        "schema_version": 1,
        "action": action.value,
        "human_review_required": review,
        "evidence_ids": [item.evidence_id for item in validated.evidence],
        "contract": contract_to_mapping(validated),
    }


@mcp.tool(name="analyze_repository_impact", structured_output=True)
async def analyze_repository_impact(
    canonical_repo: str,
    candidate_repo: str,
) -> dict[str, Any]:
    """Read and compare two disjoint repository trees using the frozen diff."""
    canonical, candidate = _repository_pair(canonical_repo, candidate_repo)
    difference = compare_repositories(canonical, candidate)
    return {
        "schema_version": 1,
        "is_clean": difference.is_clean,
        "changed_files": list(difference.changed_files),
        "modified_files": list(difference.modified_files),
        "added_files": list(difference.added_files),
        "deleted_files": list(difference.deleted_files),
    }


@mcp.tool(name="verify_result_provenance", structured_output=True)
async def verify_result_provenance(
    contract: ContractTransport,
    result: ResultTransport,
    canonical_repo: str,
    candidate_repo: str,
) -> dict[str, Any]:
    """Verify result provenance, governance, declaration, and repository state."""
    validated_contract = contract_from_mapping(_contract_mapping(contract))
    validated_result = validate_solver_result(result.model_dump(mode="python"))
    canonical, candidate = _repository_pair(canonical_repo, candidate_repo)
    difference = compare_repositories(canonical, candidate)
    expected_action = decide_change_action(validated_contract)
    expected_review = requires_human_review(expected_action)
    checks = [
        {
            "name": "action_matches_governance",
            "passed": validated_result.action == expected_action.value,
        },
        {
            "name": "evidence_ids_match_contract",
            "passed": validated_result.evidence_ids
            == tuple(item.evidence_id for item in validated_contract.evidence),
        },
        {
            "name": "human_review_matches_governance",
            "passed": validated_result.human_review_required == expected_review,
        },
        {
            "name": "declared_changes_match_repository",
            "passed": validated_result.changed_files == difference.changed_files,
        },
        {
            "name": "repository_state_matches_action",
            "passed": (
                not difference.is_clean
                if expected_action is ChangeAction.PATCH
                else difference.is_clean
            ),
        },
    ]
    return {
        "schema_version": 1,
        "passed": all(check["passed"] for check in checks),
        "expected_action": expected_action.value,
        "actual_action": validated_result.action,
        "actual_changed_files": list(difference.changed_files),
        "checks": checks,
    }


def main() -> None:
    """Run the MCP server over its default stdio transport."""
    mcp.run()


if __name__ == "__main__":
    main()
