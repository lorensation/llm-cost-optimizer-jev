import json
from argparse import Namespace
from pathlib import Path

import pytest

from scripts.final_experiment import ARMS, build_report, read_jsonl, run_experiment


@pytest.mark.asyncio
async def test_fixture_run_covers_every_arm_and_case_with_a_complete_manifest(tmp_path: Path) -> None:
    output, manifest = tmp_path / "results.jsonl", tmp_path / "manifest.json"
    args = Namespace(
        config="config/routing-claude-final.yaml", questions=Path("config/jev-routing.json"),
        input=Path("data/final_test.jsonl"), output=output, manifest=manifest, arms=None,
        limit=4, real=False, max_budget_microusd=None, concurrency=4,
    )
    await run_experiment(args)
    rows = read_jsonl(output)
    assert len(rows) == 4 * len(ARMS)
    assert {row["arm"] for row in rows} == set(ARMS)
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_data["observed_rows"] == manifest_data["expected_rows"]
    assert manifest_data["complete_cost"] is True


@pytest.mark.asyncio
async def test_fixture_run_is_resumable_without_repeating_completed_case_arm_pairs(tmp_path: Path) -> None:
    output, manifest = tmp_path / "results.jsonl", tmp_path / "manifest.json"
    args = Namespace(
        config="config/routing-claude-final.yaml", questions=Path("config/jev-routing.json"),
        input=Path("data/final_test.jsonl"), output=output, manifest=manifest, arms=["fixed_strong"],
        limit=3, real=False, max_budget_microusd=None, concurrency=4,
    )
    await run_experiment(args)
    first = read_jsonl(output)
    await run_experiment(args)
    second = read_jsonl(output)
    assert len(first) == len(second) == 3


@pytest.mark.asyncio
async def test_code_request_family_always_resolves_to_strong_given_its_pilot_profile(tmp_path: Path) -> None:
    output, manifest = tmp_path / "results.jsonl", tmp_path / "manifest.json"
    args = Namespace(
        config="config/routing-claude-final.yaml", questions=Path("config/jev-routing.json"),
        input=Path("data/final_test.jsonl"), output=output, manifest=manifest, arms=["jev_gated"],
        limit=None, real=False, max_budget_microusd=None, concurrency=4,
    )
    cases = [row for row in read_jsonl(Path("data/final_test.jsonl")) if row["contract_id"] == "classify_code_request_v1"]
    args.limit = None
    # Run against the small slice only by pre-filtering the input file into a temp dataset.
    small_input = tmp_path / "code_only.jsonl"
    small_input.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases[:3]), encoding="utf-8")
    args.input = small_input
    await run_experiment(args)
    rows = read_jsonl(output)
    assert all(row["aliases_tried"] == ["strong"] for row in rows)


def test_report_summarizes_systems_families_and_the_qa_gate_hypothesis(tmp_path: Path) -> None:
    results = tmp_path / "results.jsonl"
    rows = [
        {"case_id": "a", "group_id": "g1", "contract_id": "context_qa_v1", "arm": "jev_gated",
         "success": True, "contract_passed": True, "total_cost_microusd": 100, "latency_ms": 50,
         "router_used_default": False, "router_cost_microusd": 0, "gate_escalated": False, "gate_cost_microusd": 20},
        {"case_id": "a", "group_id": "g1", "contract_id": "context_qa_v1", "arm": "fixed_balanced",
         "success": True, "contract_passed": True, "total_cost_microusd": 300, "latency_ms": 80,
         "router_used_default": False, "router_cost_microusd": 0, "gate_escalated": False, "gate_cost_microusd": 0},
    ]
    results.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    report_path = tmp_path / "report.md"
    build_report(Namespace(input=Path("data/final_test.jsonl"), results=results, report=report_path))
    text = report_path.read_text(encoding="utf-8")
    assert "jev_gated" in text and "fixed_balanced" in text
    assert "hypothesis" in text.lower()
