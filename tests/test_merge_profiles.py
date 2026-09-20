import json
from pathlib import Path

import pytest

from scripts.merge_profiles import merge_profiles


def write_manifest(path: Path, **overrides) -> Path:
    base = {
        "validated_for_active": False, "dataset_sha256": "d", "results_sha256": "r",
        "results_file_sha256": "rf", "config_sha256": "c", "evaluator_sha256": "e",
        "experiment": {"provider": "openrouter", "models": {"economy": "m"}},
        "profiles": [{"contract_id": "x", "model_alias": "economy", "successes": 1, "sample_size": 1,
                      "quality_lower_bound": 0.5, "p95_latency_ms": 100, "expected_cost_microusd": 10,
                      "qualified_fallback": False}],
    }
    base.update(overrides)
    path.write_text(json.dumps(base), encoding="utf-8")
    return path


def test_merge_combines_disjoint_contract_profiles_and_tracks_provenance(tmp_path) -> None:
    first = write_manifest(tmp_path / "a.json")
    second = write_manifest(tmp_path / "b.json", profiles=[
        {"contract_id": "y", "model_alias": "economy", "successes": 1, "sample_size": 1,
         "quality_lower_bound": 0.5, "p95_latency_ms": 100, "expected_cost_microusd": 10, "qualified_fallback": False}
    ])
    merged = merge_profiles([first, second])
    assert merged["validated_for_active"] is False
    assert len(merged["profiles"]) == 2
    assert len(merged["sources"]) == 2
    assert {p["contract_id"] for p in merged["profiles"]} == {"x", "y"}


def test_merge_rejects_overlapping_contract_model_pairs(tmp_path) -> None:
    first = write_manifest(tmp_path / "a.json")
    second = write_manifest(tmp_path / "b.json")  # same contract_id/model_alias as first
    with pytest.raises(SystemExit):
        merge_profiles([first, second])


def test_merge_rejects_a_manifest_already_marked_validated_for_active(tmp_path) -> None:
    bad = write_manifest(tmp_path / "a.json", validated_for_active=True)
    with pytest.raises(SystemExit):
        merge_profiles([bad])


def test_merge_rejects_inconsistent_generation_settings(tmp_path) -> None:
    first = write_manifest(tmp_path / "a.json")
    second = write_manifest(tmp_path / "b.json", experiment={"provider": "different", "models": {}},
                             profiles=[{"contract_id": "y", "model_alias": "economy", "successes": 1,
                                        "sample_size": 1, "quality_lower_bound": 0.5, "p95_latency_ms": 100,
                                        "expected_cost_microusd": 10, "qualified_fallback": False}])
    with pytest.raises(SystemExit):
        merge_profiles([first, second])
