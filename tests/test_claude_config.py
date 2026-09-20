import json
from pathlib import Path

import pytest

from app.config import load_config, load_contracts, load_profiles
from app.routing import RoutingPolicy


def test_real_smoke_config_pins_current_claude_pool() -> None:
    config = load_config("config/real-smoke.yaml")
    assert config.mode == "fixture"
    assert config.models["economy"].model_id == "anthropic/claude-haiku-4.5"
    assert config.models["balanced"].model_id == "anthropic/claude-sonnet-5"
    assert config.models["strong"].model_id == "anthropic/claude-opus-5"
    assert all(model.provider == "openrouter" for model in config.models.values())


def test_bootstrap_routing_shape_uses_all_three_tiers() -> None:
    config = load_config("config/real-smoke.yaml")
    contracts = load_contracts(config.contracts_dir)
    _, profiles = load_profiles(config.profiles_path, contracts, config.models)
    router = RoutingPolicy(config.models, profiles)
    extraction = router.select(contracts["extract_invoice_v1"], 50_000, 60_000)
    qa = router.select(contracts["context_qa_v1"], 50_000, 60_000)
    assert (extraction.primary, extraction.fallback) == ("economy", "strong")
    assert (qa.primary, qa.fallback) == ("balanced", "strong")


def test_bootstrap_profiles_cannot_be_marked_active(tmp_path, monkeypatch) -> None:
    source = Path("config/real-smoke.yaml").read_text(encoding="utf-8")
    path = tmp_path / "active.yaml"
    path.write_text(source.replace("mode: fixture", "mode: active"), encoding="utf-8")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only")
    with pytest.raises(ValueError, match="validated_for_active"):
        load_config(path)


def test_catalog_snapshot_matches_configured_rates() -> None:
    config = load_config("config/real-smoke.yaml")
    snapshot = json.loads(Path("config/model-snapshots/openrouter-claude-2026-09-20.json").read_text(encoding="utf-8"))
    for item in snapshot["models"]:
        model = config.models[item["alias"]]
        assert model.model_id == item["id"]
        assert model.input_microusd_per_million == round(float(item["pricing"]["prompt"]) * 1_000_000_000_000)
        assert model.output_microusd_per_million == round(float(item["pricing"]["completion"]) * 1_000_000_000_000)
