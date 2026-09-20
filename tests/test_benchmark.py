import json
from pathlib import Path

from app.config import load_contracts
from scripts.benchmark import evaluate, public_request, read_jsonl, wilson_lower


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
