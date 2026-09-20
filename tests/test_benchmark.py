import json
from argparse import Namespace
from pathlib import Path

from app.config import load_contracts
from scripts.benchmark import build_profiles, build_report, evaluate, file_hash, public_request, read_jsonl, wilson_lower


def test_pilot_dataset_has_balanced_first_twenty_and_no_unresolved_labels() -> None:
    rows = read_jsonl(Path("data/pilot.jsonl"))
    assert len(rows) == 100
    assert len({row["id"] for row in rows}) == 100
    assert {row["contract_id"] for row in rows[:20]} == {
        "extract_invoice_v1", "classify_ticket_v1", "context_qa_v1"
    }
    assert sum(row["contract_id"] == "extract_invoice_v1" for row in rows) == 40
    assert sum(row["contract_id"] == "classify_ticket_v1" for row in rows) == 30
    assert sum(row["contract_id"] == "context_qa_v1" for row in rows) == 30
    assert all(row["label_status"] == "resolved" for row in rows)
    assert any(row["adversarial"] for row in rows)


def test_gold_is_never_in_public_request() -> None:
    case = read_jsonl(Path("data/pilot.jsonl"))[0]
    contract = load_contracts(Path("contracts"))[case["contract_id"]]
    request = json.loads(public_request(case, contract))
    assert "expected" not in request
    assert "label_status" not in request
    assert request["requirements"] == case["requirements"]


def test_evaluator_separates_schema_and_semantic_correctness() -> None:
    contracts = load_contracts(Path("contracts"))
    extraction = next(row for row in read_jsonl(Path("data/pilot.jsonl")) if row["contract_id"] == "extract_invoice_v1")
    contract = contracts[extraction["contract_id"]]
    assert evaluate(extraction, contract, extraction["expected"])[0]
    valid_but_wrong = {"invoice_number": "WRONG", "total": extraction["expected"]["total"]}
    passed, reasons = evaluate(extraction, contract, valid_but_wrong)
    assert not passed and reasons == ["invoice_number"]


def test_wilson_lower_is_conservative() -> None:
    assert 0.88 < wilson_lower(30, 30) < 1
    assert wilson_lower(0, 30) == 0


def test_full_pilot_report_and_profiles_capture_the_decision(tmp_path: Path) -> None:
    results = Path("artifacts/pilot/results.jsonl")
    report = tmp_path / "report.md"
    profiles = tmp_path / "profiles.json"
    common = {
        "input": Path("data/pilot.jsonl"),
        "results": results,
        "config": "config/pilot-claude.yaml",
    }

    build_report(Namespace(**common, output=report))
    build_profiles(Namespace(**common, output=profiles))

    report_text = report.read_text(encoding="utf-8")
    profile_data = json.loads(profiles.read_text(encoding="utf-8"))
    assert "| proposed contract route | 100/100 | 83444 |" in report_text
    assert "**39.2% less**" in report_text
    assert "**`continue_router`**" in report_text
    assert profile_data["validated_for_active"] is False
    assert profile_data["results_sha256"] == file_hash(results)
    assert len(profile_data["profiles"]) == 9
