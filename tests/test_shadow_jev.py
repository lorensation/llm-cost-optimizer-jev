import json
from argparse import Namespace
from pathlib import Path

import pytest

from scripts.shadow_jev import build_report, estimated_decision_cost, read_jsonl, run_shadow


def test_estimated_decision_cost_scales_with_text_length() -> None:
    short = {"request": "r", "source": "s"}
    long = {"request": "r" * 500, "source": "s" * 2000}
    assert estimated_decision_cost(short, questions_chars=100) < estimated_decision_cost(long, questions_chars=100)
    assert estimated_decision_cost(short, questions_chars=100) > 0


@pytest.mark.asyncio
async def test_fixture_shadow_run_produces_complete_manifest_and_report(tmp_path: Path) -> None:
    output, manifest, report = tmp_path / "results.jsonl", tmp_path / "manifest.json", tmp_path / "report.md"
    args = Namespace(
        config="config/routing-claude-shadow.yaml", questions=Path("config/jev-routing.json"),
        input=Path("data/pilot.jsonl"), output=output, manifest=manifest, limit=6,
        real=False, max_budget_microusd=None, concurrency=4,
    )
    await run_shadow(args)
    rows = read_jsonl(output)
    assert len(rows) == 6
    assert all(row["jev_status"] == "evaluated" for row in rows)
    assert all(row["local_route"] is not None for row in rows)
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_data["mode"] == "fixture"
    assert manifest_data["observed_rows"] == manifest_data["expected_rows"] == 6
    assert manifest_data["complete_cost"] is True

    build_report(Namespace(questions=Path("config/jev-routing.json"), input=Path("data/pilot.jsonl"),
                            results=output, report=report))
    report_text = report.read_text(encoding="utf-8")
    assert "Diagnostic only" in report_text
    assert "Interpretation and limitations" in report_text


@pytest.mark.asyncio
async def test_shadow_run_is_resumable_and_does_not_repay_completed_cases(tmp_path: Path) -> None:
    output, manifest = tmp_path / "results.jsonl", tmp_path / "manifest.json"
    args = Namespace(
        config="config/routing-claude-shadow.yaml", questions=Path("config/jev-routing.json"),
        input=Path("data/pilot.jsonl"), output=output, manifest=manifest, limit=3,
        real=False, max_budget_microusd=None, concurrency=4,
    )
    await run_shadow(args)
    first_pass_rows = read_jsonl(output)
    await run_shadow(args)
    second_pass_rows = read_jsonl(output)
    assert len(first_pass_rows) == len(second_pass_rows) == 3
