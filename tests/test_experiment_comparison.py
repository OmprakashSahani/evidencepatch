import json
import math
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

import evidencepatch.experiment_comparison as module
from evidencepatch.experiment_comparison import (
    CaseOutcomeDelta,
    CheckMetricDelta,
    ExperimentComparison,
    compare_experiment_summaries,
    comparison_to_mapping,
    comparison_to_markdown,
    write_comparison_json,
    write_comparison_markdown,
    write_comparison_report,
)


CHECKS = ("action_correct", "hidden_behavior_passed")


def summaries(*, baseline=(True, False, False), advanced=(True, True, False),
              model="synthetic-model", baseline_duration=10.0, advanced_duration=20.0,
              advanced_calls=(1, 2, 1)):
    ids = ("alpha", "beta", "gamma")
    def cases(values, advanced_rows=False):
        rows = []
        for index, (case_id, passed) in enumerate(zip(ids, values, strict=True)):
            row = {"case_id": case_id, "verified_success": passed,
                   "failed_checks": [] if passed else [CHECKS[index % 2]]}
            if advanced_rows: row["codex_call_count"] = advanced_calls[index]
            rows.append(row)
        return rows
    def metrics(values):
        return [{"name": name, "passed_cases": count, "total_cases": 3, "rate": count / 3}
                for name, count in zip(CHECKS, values, strict=True)]
    b_success = sum(baseline); a_success = sum(advanced)
    baseline_summary = {
        "schema_version": 1, "experiment": "plain_codex_baseline", "model": model,
        "total_cases": 3, "verified_successes": b_success,
        "verified_failures": 3 - b_success, "vusr": b_success / 3,
        "total_duration_seconds": baseline_duration,
        "check_metrics": metrics((2, 1)), "cases": cases(baseline),
    }
    advanced_summary = {
        "schema_version": 1, "experiment": "evidencepatch_advanced", "model": model,
        "total_cases": 3, "verified_successes": a_success,
        "verified_failures": 3 - a_success, "vusr": a_success / 3,
        "total_codex_calls": sum(advanced_calls),
        "total_codex_duration_seconds": advanced_duration,
        "check_metrics": metrics((3, 2)), "cases": cases(advanced, True),
    }
    return baseline_summary, advanced_summary


def write_summaries(tmp_path: Path, **kwargs):
    baseline, advanced = summaries(**kwargs)
    bpath, apath = tmp_path / "baseline.json", tmp_path / "advanced.json"
    bpath.write_text(json.dumps(baseline), encoding="utf-8")
    apath.write_text(json.dumps(advanced), encoding="utf-8")
    return bpath, apath, baseline, advanced


def test_valid_comparison_derives_reliability_cost_and_duration(tmp_path: Path) -> None:
    bpath, apath, _, _ = write_summaries(tmp_path)
    value = compare_experiment_summaries(bpath, apath)
    assert value.baseline_vusr == 1 / 3 and value.advanced_vusr == 2 / 3
    assert value.vusr_absolute_delta == 1 / 3
    assert value.vusr_percentage_point_delta == pytest.approx(100 / 3)
    assert value.failure_reduction_count == 1 and value.failure_reduction_rate == 0.5
    assert value.baseline_total_codex_calls == 3 and value.advanced_total_codex_calls == 4
    assert value.codex_call_delta == 1 and value.codex_call_ratio == 4 / 3
    assert value.duration_delta_seconds == 10 and value.duration_ratio == 2


@pytest.mark.parametrize("baseline,advanced,expected", [
    ((True, False, False), (True, True, False), 1 / 3),
    ((True, False, False), (True, False, False), 0.0),
    ((True, True, False), (True, False, False), -1 / 3),
])
def test_positive_zero_and_negative_vusr_delta(tmp_path: Path, baseline, advanced, expected) -> None:
    bpath, apath, _, _ = write_summaries(tmp_path, baseline=baseline, advanced=advanced)
    assert compare_experiment_summaries(bpath, apath).vusr_absolute_delta == expected


def test_zero_baseline_failures_has_no_reduction_rate(tmp_path: Path) -> None:
    all_pass = (True, True, True)
    bpath, apath, _, _ = write_summaries(tmp_path, baseline=all_pass, advanced=all_pass)
    assert compare_experiment_summaries(bpath, apath).failure_reduction_rate is None


def test_metric_order_and_deltas(tmp_path: Path) -> None:
    bpath, apath, _, _ = write_summaries(tmp_path)
    metrics = compare_experiment_summaries(bpath, apath).check_metric_deltas
    assert tuple(item.name for item in metrics) == CHECKS
    assert metrics[0].baseline_passed_cases == 2 and metrics[0].advanced_passed_cases == 3
    assert metrics[0].percentage_point_delta == 100 * (1 - 2 / 3)


def test_all_case_outcomes_and_order(tmp_path: Path) -> None:
    outcomes = [
        CaseOutcomeDelta("improved", False, True, ("check",), ()),
        CaseOutcomeDelta("regressed", True, False, (), ("check",)),
        CaseOutcomeDelta("success", True, True, (), ()),
        CaseOutcomeDelta("failure", False, False, ("check",), ("check",)),
    ]
    assert [item.outcome for item in outcomes] == [
        "IMPROVED", "REGRESSED", "UNCHANGED_SUCCESS", "UNCHANGED_FAILURE"
    ]
    bpath, apath, _, _ = write_summaries(tmp_path)
    assert tuple(item.case_id for item in compare_experiment_summaries(bpath, apath).case_outcome_deltas) == ("alpha", "beta", "gamma")


def mutate_and_compare(tmp_path: Path, target: str, mutator):
    bpath, apath, baseline, advanced = write_summaries(tmp_path)
    data = baseline if target == "baseline" else advanced
    mutator(data)
    (bpath if target == "baseline" else apath).write_text(json.dumps(data), encoding="utf-8")
    return lambda: compare_experiment_summaries(bpath, apath)


def test_same_model_required(tmp_path: Path) -> None:
    invoke = mutate_and_compare(tmp_path, "advanced", lambda data: data.update(model="other"))
    with pytest.raises(ValueError, match="same model"): invoke()


def test_same_total_cases_required(tmp_path: Path) -> None:
    def mutate(data):
        data["total_cases"] = 2; data["verified_failures"] = 0
        data["vusr"] = 1.0
        data["cases"] = data["cases"][:2]
        data["total_codex_calls"] = sum(case["codex_call_count"] for case in data["cases"])
        for metric in data["check_metrics"]:
            metric["total_cases"] = 2
            metric["passed_cases"] = min(metric["passed_cases"], 2)
            metric["rate"] = metric["passed_cases"] / 2
    invoke = mutate_and_compare(tmp_path, "advanced", mutate)
    with pytest.raises(ValueError, match="same total_cases"): invoke()


@pytest.mark.parametrize("mutation", ["id", "order"])
def test_same_case_ids_and_order_required(tmp_path: Path, mutation: str) -> None:
    def mutate(data):
        if mutation == "id": data["cases"][0]["case_id"] = "different"
        else: data["cases"][0], data["cases"][1] = data["cases"][1], data["cases"][0]
    invoke = mutate_and_compare(tmp_path, "advanced", mutate)
    with pytest.raises(ValueError, match="case IDs"): invoke()


@pytest.mark.parametrize("mutation", ["name", "order"])
def test_same_check_names_and_order_required(tmp_path: Path, mutation: str) -> None:
    def mutate(data):
        if mutation == "name": data["check_metrics"][0]["name"] = "different"
        else: data["check_metrics"].reverse()
    invoke = mutate_and_compare(tmp_path, "advanced", mutate)
    with pytest.raises(ValueError, match="check names"): invoke()


@pytest.mark.parametrize("which,payload,match", [
    ("baseline", "{bad", "invalid JSON"),
    ("advanced", "[]", "JSON object"),
])
def test_malformed_or_nonobject_json_rejected(tmp_path: Path, which: str, payload: str, match: str) -> None:
    bpath, apath, _, _ = write_summaries(tmp_path)
    (bpath if which == "baseline" else apath).write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError, match=match): compare_experiment_summaries(bpath, apath)


@pytest.mark.parametrize("target,field,value,match", [
    ("baseline", "experiment", "wrong", "experiment"),
    ("advanced", "experiment", "wrong", "experiment"),
    ("baseline", "schema_version", 2, "schema_version"),
    ("advanced", "schema_version", True, "schema_version"),
    ("baseline", "vusr", 0.9, "vusr"),
])
def test_identity_schema_and_vusr_validation(tmp_path: Path, target: str, field: str, value, match: str) -> None:
    invoke = mutate_and_compare(tmp_path, target, lambda data: data.update({field: value}))
    with pytest.raises(ValueError, match=match): invoke()


def test_success_failure_arithmetic_rejected(tmp_path: Path) -> None:
    invoke = mutate_and_compare(tmp_path, "baseline", lambda data: data.update(verified_failures=0))
    with pytest.raises(ValueError, match="sum"): invoke()


def test_invalid_metric_total_rejected(tmp_path: Path) -> None:
    invoke = mutate_and_compare(tmp_path, "advanced", lambda data: data["check_metrics"][0].update(total_cases=2))
    with pytest.raises(ValueError, match="metric totals"): invoke()


@pytest.mark.parametrize("failed", [["x", "x"], [" "]])
def test_invalid_failed_checks_rejected(tmp_path: Path, failed) -> None:
    invoke = mutate_and_compare(tmp_path, "baseline", lambda data: data["cases"][1].update(failed_checks=failed))
    with pytest.raises(ValueError, match="failed_checks"): invoke()


def test_advanced_total_call_mismatch_rejected(tmp_path: Path) -> None:
    invoke = mutate_and_compare(tmp_path, "advanced", lambda data: data.update(total_codex_calls=99))
    with pytest.raises(ValueError, match="does not match"): invoke()


@pytest.mark.parametrize("target,field,value", [
    ("baseline", "total_duration_seconds", math.inf),
    ("advanced", "total_codex_duration_seconds", math.nan),
    ("baseline", "total_duration_seconds", -1),
    ("advanced", "total_codex_duration_seconds", -1),
    ("baseline", "total_duration_seconds", 0),
])
def test_invalid_durations_rejected(tmp_path: Path, target: str, field: str, value) -> None:
    invoke = mutate_and_compare(tmp_path, target, lambda data: data.update({field: value}))
    with pytest.raises(ValueError): invoke()


def test_wrong_input_types_missing_symlink_and_directory_rejected(tmp_path: Path) -> None:
    bpath, apath, _, _ = write_summaries(tmp_path)
    with pytest.raises(ValueError, match="pathlib.Path"): compare_experiment_summaries("bad", apath)  # type: ignore[arg-type]
    with pytest.raises(FileNotFoundError): compare_experiment_summaries(tmp_path / "missing", apath)
    with pytest.raises(ValueError, match="regular file"): compare_experiment_summaries(tmp_path, apath)
    link = tmp_path / "link"; link.symlink_to(bpath)
    with pytest.raises(ValueError, match="symlink"): compare_experiment_summaries(link, apath)


def test_mapping_and_rendering_are_deterministic(tmp_path: Path) -> None:
    bpath, apath, _, _ = write_summaries(tmp_path)
    value = compare_experiment_summaries(bpath, apath)
    assert comparison_to_mapping(value) == comparison_to_mapping(value)
    assert comparison_to_markdown(value) == comparison_to_markdown(value)
    assert comparison_to_mapping(value)["comparison"] == "plain_codex_baseline_vs_evidencepatch_advanced"


def test_markdown_contains_metrics_tradeoff_cases_and_notes(tmp_path: Path) -> None:
    bpath, apath, _, _ = write_summaries(tmp_path)
    text = comparison_to_markdown(compare_experiment_summaries(bpath, apath))
    assert "# EvidencePatch Measured Improvement" in text
    assert "## Primary Metric" in text and "## Cost Tradeoff" in text
    assert "`beta` — IMPROVED" in text
    assert "same benchmark case list" in text and "same model" in text
    assert "does not rerun a solver" in text and "reads no hidden ground truth" in text
    assert "reliability-versus-compute tradeoff" in text
    assert "expected action" not in text.lower()
    assert "establish statistical significance" in text


def test_safe_json_and_markdown_writers(tmp_path: Path) -> None:
    bpath, apath, _, _ = write_summaries(tmp_path)
    value = compare_experiment_summaries(bpath, apath)
    json_path, md_path = tmp_path / "report.json", tmp_path / "report.md"
    assert write_comparison_json(value, json_path) == json_path.resolve()
    assert write_comparison_markdown(value, md_path) == md_path.resolve()
    assert json_path.read_text().endswith("\n") and md_path.read_text().endswith("\n")
    with pytest.raises(ValueError, match="already exist"): write_comparison_json(value, json_path)
    with pytest.raises(ValueError, match="already exist"): write_comparison_markdown(value, md_path)


def test_writer_rejects_symlink_and_missing_parent(tmp_path: Path) -> None:
    bpath, apath, _, _ = write_summaries(tmp_path)
    value = compare_experiment_summaries(bpath, apath)
    target = tmp_path / "target"; target.write_text("x")
    link = tmp_path / "link"; link.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"): write_comparison_json(value, link)
    with pytest.raises(ValueError, match="parent"): write_comparison_markdown(value, tmp_path / "missing" / "report.md")


def test_report_writer_creates_exact_files_and_refuses_existing(tmp_path: Path) -> None:
    bpath, apath, _, _ = write_summaries(tmp_path)
    output = tmp_path / "output"; output.mkdir()
    paths = write_comparison_report(bpath, apath, output)
    assert tuple(path.name for path in paths) == ("comparison.json", "comparison.md")
    assert {path.name for path in output.iterdir()} == {"comparison.json", "comparison.md"}
    with pytest.raises(ValueError, match="must not already exist"): write_comparison_report(bpath, apath, output)


def comparison_value(tmp_path: Path) -> ExperimentComparison:
    bpath, apath, _, _ = write_summaries(tmp_path)
    return compare_experiment_summaries(bpath, apath)


@pytest.mark.parametrize("value", [True, -1, 4])
def test_check_metric_strict_validation(value) -> None:
    with pytest.raises(ValueError): CheckMetricDelta("metric", value, 1, 3, 1/3, 1/3, 0, 0)


@pytest.mark.parametrize("field,value", [
    ("case_id", " "), ("baseline_verified_success", 1),
    ("baseline_failed_checks", ["check"]),
])
def test_case_delta_strict_validation(field: str, value) -> None:
    kwargs = dict(case_id="case", baseline_verified_success=True,
        advanced_verified_success=False, baseline_failed_checks=(), advanced_failed_checks=("check",))
    kwargs[field] = value
    with pytest.raises(ValueError): CaseOutcomeDelta(**kwargs)


@pytest.mark.parametrize("field,value", [
    ("baseline_summary_path", "path"), ("baseline_model", " "),
    ("baseline_total_cases", True), ("baseline_vusr", math.inf),
    ("check_metric_deltas", ()), ("case_outcome_deltas", ()),
])
def test_comparison_strict_validation(tmp_path: Path, field: str, value) -> None:
    good = comparison_value(tmp_path)
    kwargs = {item.name: getattr(good, item.name) for item in fields(good)}; kwargs[field] = value
    with pytest.raises(ValueError): ExperimentComparison(**kwargs)


def test_dataclasses_are_immutable(tmp_path: Path) -> None:
    comparison = comparison_value(tmp_path)
    with pytest.raises(FrozenInstanceError): comparison.baseline_vusr = 0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError): comparison.check_metric_deltas[0].name = "x"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError): comparison.case_outcome_deltas[0].case_id = "x"  # type: ignore[misc]


def test_source_is_reporting_only_and_has_no_private_or_case_specific_logic() -> None:
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    for forbidden in (
        "run_codex", "run_baseline_benchmark", "run_advanced_benchmark",
        "evaluate_case", "ground_truth", "case_10",
    ):
        assert forbidden not in source
