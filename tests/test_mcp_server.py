import shutil
from pathlib import Path

import pytest
from mcp import Client

import evidencepatch.mcp_server as server
from evidencepatch.mcp_server import mcp


@pytest.fixture
def anyio_backend():
    return "asyncio"


def contract(kind: str = "PATCH", ids=("SOURCE-A", "SOURCE-B")) -> dict[str, object]:
    patch = kind == "PATCH"
    escalate = kind == "ESCALATE"
    return {
        "evidence": [
            {
                "evidence_id": evidence_id,
                "authority": "DRAFT" if escalate else "AUTHORITATIVE",
                "status": "PROVISIONAL" if escalate else "CURRENT",
                "proposes_executable_change": patch or escalate,
                "conflicts_with_current_authority": False,
            }
            for evidence_id in ids
        ],
        "executable_behavior_change": patch,
        "semantic_equivalence": kind == "NO_PATCH",
        "unresolved_conflict": False,
        "ambiguous_or_incomplete": False,
        "rationale": "Generic structured evidence rationale.",
    }


def repos(tmp_path: Path, *, dirty=False) -> tuple[Path, Path]:
    canonical = tmp_path / "canonical"
    candidate = tmp_path / "candidate"
    canonical.mkdir()
    (canonical / "rule.py").write_text("VALUE = 1\n", encoding="utf-8")
    shutil.copytree(canonical, candidate)
    if dirty:
        (candidate / "rule.py").write_text("VALUE = 2\n", encoding="utf-8")
    return canonical, candidate


async def call(name: str, arguments: dict[str, object]):
    async with Client(mcp) as client:
        return await client.call_tool(name, arguments)


@pytest.mark.anyio
async def test_server_lists_exactly_three_tools() -> None:
    async with Client(mcp) as client:
        listed = await client.list_tools()
    assert {tool.name for tool in listed.tools} == {
        "assess_change_contract",
        "analyze_repository_impact",
        "verify_result_provenance",
    }
    assert len(listed.tools) == 3


@pytest.mark.anyio
@pytest.mark.parametrize(
    "kind,review", [("PATCH", True), ("NO_PATCH", False), ("ESCALATE", True)]
)
async def test_assess_contract_actions_and_structured_content(kind: str, review: bool) -> None:
    response = await call("assess_change_contract", {"contract": contract(kind)})
    assert not response.is_error
    assert response.structured_content["action"] == kind
    assert response.structured_content["human_review_required"] is review
    assert response.structured_content["evidence_ids"] == ["SOURCE-A", "SOURCE-B"]
    assert response.structured_content["contract"]["schema_version"] == 1


@pytest.mark.anyio
async def test_assess_uses_frozen_gate_and_review_once(monkeypatch: pytest.MonkeyPatch) -> None:
    gate_calls = []
    review_calls = []
    real_gate = server.decide_change_action
    real_review = server.requires_human_review
    monkeypatch.setattr(server, "decide_change_action", lambda value: gate_calls.append(value) or real_gate(value))
    monkeypatch.setattr(server, "requires_human_review", lambda value: review_calls.append(value) or real_review(value))
    response = await call("assess_change_contract", {"contract": contract("NO_PATCH")})
    assert not response.is_error
    assert len(gate_calls) == len(review_calls) == 1


@pytest.mark.anyio
async def test_invalid_contract_is_mcp_error() -> None:
    invalid = contract(); invalid["semantic_equivalence"] = True
    response = await call("assess_change_contract", {"contract": invalid})
    assert response.is_error


@pytest.mark.anyio
async def test_repository_impact_clean_structured_content(tmp_path: Path) -> None:
    canonical, candidate = repos(tmp_path)
    response = await call("analyze_repository_impact", {
        "canonical_repo": str(canonical), "candidate_repo": str(candidate)})
    assert not response.is_error
    assert response.structured_content == {
        "schema_version": 1, "is_clean": True, "changed_files": [],
        "modified_files": [], "added_files": [], "deleted_files": [],
    }


@pytest.mark.anyio
async def test_repository_impact_all_change_types_and_order(tmp_path: Path) -> None:
    canonical, candidate = repos(tmp_path)
    (canonical / "deleted.py").write_text("old", encoding="utf-8")
    shutil.copy2(canonical / "deleted.py", candidate / "deleted.py")
    (candidate / "rule.py").write_text("changed", encoding="utf-8")
    (candidate / "added.py").write_text("new", encoding="utf-8")
    (candidate / "deleted.py").unlink()
    response = await call("analyze_repository_impact", {
        "canonical_repo": str(canonical), "candidate_repo": str(candidate)})
    data = response.structured_content
    assert data["modified_files"] == ["rule.py"]
    assert data["added_files"] == ["added.py"]
    assert data["deleted_files"] == ["deleted.py"]
    assert data["changed_files"] == ["added.py", "deleted.py", "rule.py"]


@pytest.mark.anyio
@pytest.mark.parametrize("invalid_kind", ["missing", "file", "symlink"])
async def test_invalid_repository_root_is_mcp_error(tmp_path: Path, invalid_kind: str) -> None:
    canonical, candidate = repos(tmp_path)
    if invalid_kind == "missing": bad = tmp_path / "missing"
    elif invalid_kind == "file": bad = canonical / "rule.py"
    else:
        bad = tmp_path / "link"; bad.symlink_to(canonical, target_is_directory=True)
    response = await call("analyze_repository_impact", {
        "canonical_repo": str(bad), "candidate_repo": str(candidate)})
    assert response.is_error


@pytest.mark.anyio
@pytest.mark.parametrize("relationship", ["equal", "canonical_contains", "candidate_contains"])
async def test_repository_overlap_is_mcp_error(tmp_path: Path, relationship: str) -> None:
    if relationship == "equal":
        canonical = candidate = tmp_path
    elif relationship == "canonical_contains":
        canonical = tmp_path / "root"; candidate = canonical / "child"; candidate.mkdir(parents=True)
    else:
        candidate = tmp_path / "root"; canonical = candidate / "child"; canonical.mkdir(parents=True)
    response = await call("analyze_repository_impact", {
        "canonical_repo": str(canonical), "candidate_repo": str(candidate)})
    assert response.is_error


def result(kind: str, changed: list[str], ids=None, review=None) -> dict[str, object]:
    return {
        "schema_version": 1,
        "action": kind,
        "changed_files": changed,
        "evidence_ids": ids if ids is not None else ["SOURCE-A", "SOURCE-B"],
        "human_review_required": review if review is not None else kind != "NO_PATCH",
        "summary": "Deterministic proposed result.",
    }


@pytest.mark.anyio
@pytest.mark.parametrize("kind,dirty", [("PATCH", True), ("NO_PATCH", False), ("ESCALATE", False)])
async def test_valid_provenance_passes_all_ordered_checks(tmp_path: Path, kind: str, dirty: bool) -> None:
    canonical, candidate = repos(tmp_path, dirty=dirty)
    changed = ["rule.py"] if dirty else []
    response = await call("verify_result_provenance", {
        "contract": contract(kind), "result": result(kind, changed),
        "canonical_repo": str(canonical), "candidate_repo": str(candidate),
    })
    data = response.structured_content
    assert data["passed"] is True
    assert [item["name"] for item in data["checks"]] == [
        "action_matches_governance", "evidence_ids_match_contract",
        "human_review_matches_governance", "declared_changes_match_repository",
        "repository_state_matches_action",
    ]
    assert all(item["passed"] for item in data["checks"])


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["action", "evidence", "review", "undeclared", "nonexistent"])
async def test_provenance_individual_mismatch_checks(tmp_path: Path, failure: str) -> None:
    canonical, candidate = repos(tmp_path, dirty=True)
    proposed = result("PATCH", ["rule.py"])
    if failure == "action": proposed = result("ESCALATE", [])
    elif failure == "evidence": proposed["evidence_ids"] = ["SOURCE-A"]
    elif failure == "review": proposed["human_review_required"] = False
    elif failure == "undeclared":
        (candidate / "additional.py").write_text("new", encoding="utf-8")
    elif failure == "nonexistent": proposed["changed_files"] = ["missing.py"]
    response = await call("verify_result_provenance", {
        "contract": contract("PATCH"), "result": proposed,
        "canonical_repo": str(canonical), "candidate_repo": str(candidate),
    })
    checks = {item["name"]: item["passed"] for item in response.structured_content["checks"]}
    expected = {
        "action": "action_matches_governance", "evidence": "evidence_ids_match_contract",
        "review": "human_review_matches_governance",
        "undeclared": "declared_changes_match_repository",
        "nonexistent": "declared_changes_match_repository",
    }[failure]
    assert checks[expected] is False
    assert response.structured_content["passed"] is False


@pytest.mark.anyio
@pytest.mark.parametrize("kind,dirty", [("PATCH", False), ("NO_PATCH", True), ("ESCALATE", True)])
async def test_repository_state_mismatch_fails(tmp_path: Path, kind: str, dirty: bool) -> None:
    canonical, candidate = repos(tmp_path, dirty=dirty)
    # Keep the proposed result schema valid even when repository state is inconsistent.
    declared = ["synthetic.py"] if kind == "PATCH" else []
    response = await call("verify_result_provenance", {
        "contract": contract(kind), "result": result(kind, declared),
        "canonical_repo": str(canonical), "candidate_repo": str(candidate),
    })
    checks = {item["name"]: item["passed"] for item in response.structured_content["checks"]}
    assert checks["repository_state_matches_action"] is False


@pytest.mark.anyio
@pytest.mark.parametrize("bad", ["result", "contract"])
async def test_invalid_transport_or_frozen_schema_is_mcp_error(tmp_path: Path, bad: str) -> None:
    canonical, candidate = repos(tmp_path)
    proposed_contract = contract("NO_PATCH")
    proposed_result = result("NO_PATCH", [])
    if bad == "result": proposed_result["schema_version"] = 2
    else: proposed_contract["rationale"] = " "
    response = await call("verify_result_provenance", {
        "contract": proposed_contract, "result": proposed_result,
        "canonical_repo": str(canonical), "candidate_repo": str(candidate),
    })
    assert response.is_error


@pytest.mark.anyio
async def test_repository_tools_do_not_modify_bytes(tmp_path: Path) -> None:
    canonical, candidate = repos(tmp_path, dirty=True)
    before = ((canonical / "rule.py").read_bytes(), (candidate / "rule.py").read_bytes())
    await call("analyze_repository_impact", {
        "canonical_repo": str(canonical), "candidate_repo": str(candidate)})
    await call("verify_result_provenance", {
        "contract": contract("PATCH"), "result": result("PATCH", ["rule.py"]),
        "canonical_repo": str(canonical), "candidate_repo": str(candidate)})
    after = ((canonical / "rule.py").read_bytes(), (candidate / "rule.py").read_bytes())
    assert after == before


def test_server_instructions_product_boundary() -> None:
    lowered = server.SERVER_INSTRUCTIONS.lower()
    assert "external providers such as exa" in lowered
    assert "evidence discovery" in lowered
    assert "not medical advice" in lowered


def test_main_uses_default_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(server.mcp, "run", lambda: calls.append(()))
    server.main()
    assert calls == [()]


def test_requirements_is_exact() -> None:
    assert Path("requirements.txt").read_text(encoding="utf-8") == "mcp==2.1.1\n"


def test_source_has_no_solver_network_benchmark_or_private_access() -> None:
    source = Path(server.__file__).read_text(encoding="utf-8").lower()
    for forbidden in (
        "run_codex", "run_evidencepatch_workflow", "run_contract_extraction",
        "run_authorized_patch", "evaluate_case", "run_baseline_benchmark",
        "run_advanced_benchmark", "ground_truth", "benchmark/cases",
        "web_search", "requests", "httpx",
    ):
        assert forbidden not in source
