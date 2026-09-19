from pathlib import Path

import pytest

from app.config import DuplicateKeyError, UniqueKeyLoader, load_config
from app.costs import estimate_cost_microusd, usd_to_microusd
import yaml


def test_duplicate_yaml_keys_are_rejected() -> None:
    with pytest.raises(DuplicateKeyError):
        yaml.load("mode: fixture\nmode: active\n", Loader=UniqueKeyLoader)


def test_default_config_is_valid() -> None:
    config = load_config("config/default.yaml")
    assert config.max_generations == 2
    assert config.mode == "fixture"


def test_money_units_round_without_floats() -> None:
    assert usd_to_microusd("0.000019992") == 20
    assert estimate_cost_microusd(500, 100, 100_000, 400_000) == 90

