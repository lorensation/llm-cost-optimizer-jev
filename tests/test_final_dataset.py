import json
from pathlib import Path

from app.config import load_contracts
from scripts.benchmark import read_jsonl


def load_final() -> list[dict]:
    return read_jsonl(Path("data/final_test.jsonl"))


def test_final_dataset_is_disjoint_from_the_pilot() -> None:
    final_rows, pilot_rows = load_final(), read_jsonl(Path("data/pilot.jsonl"))
    final_ids = {row["id"] for row in final_rows}
    final_groups = {row["group_id"] for row in final_rows}
    pilot_ids = {row["id"] for row in pilot_rows}
    pilot_groups = {row["group_id"] for row in pilot_rows}
    assert not (final_ids & pilot_ids)
    assert not (final_groups & pilot_groups)
    assert len(final_ids) == len(final_rows)


def test_final_dataset_has_more_groups_than_the_pilot_for_tighter_intervals() -> None:
    final_rows = load_final()
    assert len(final_rows) == 376
    assert len({row["group_id"] for row in final_rows}) == 102
    assert sum(row["contract_id"] == "extract_invoice_v1" for row in final_rows) == 96
    assert sum(row["contract_id"] == "classify_ticket_v1" for row in final_rows) == 80
    assert sum(row["contract_id"] == "context_qa_v1" for row in final_rows) == 80
    assert sum(row["contract_id"] == "classify_code_request_v1" for row in final_rows) == 120


def test_code_request_family_is_balanced_across_its_taxonomy() -> None:
    final_rows = load_final()
    code = [row for row in final_rows if row["contract_id"] == "classify_code_request_v1"]
    labels = [row["expected"]["label"] for row in code]
    for label in ("planning", "refactoring", "testing", "fix", "documentation", "other"):
        assert labels.count(label) == 20


def test_final_dataset_enriches_qa_abstention_and_documents_it_as_deliberate() -> None:
    final_rows = load_final()
    qa = [row for row in final_rows if row["contract_id"] == "context_qa_v1"]
    abstained = sum(row["expected"]["abstained"] for row in qa)
    assert abstained / len(qa) == 28 / 80


def test_final_dataset_gold_labels_are_schema_valid_and_taxonomy_valid() -> None:
    contracts = load_contracts(Path("contracts"))
    for row in load_final():
        contract = contracts[row["contract_id"]]
        if contract.family.value == "classification":
            assert row["expected"]["label"] in contract.taxonomy
        assert len(row["source"]) <= contract.max_source_chars
