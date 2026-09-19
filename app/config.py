from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.contracts import ModelProfile, TaskContract


class DuplicateKeyError(ValueError):
    pass


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise DuplicateKeyError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


class ModelConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="forbid")
    model_id: str
    provider: str
    input_microusd_per_million: int = Field(ge=0)
    output_microusd_per_million: int = Field(ge=0)
    context_tokens: int = Field(gt=0)


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="forbid", env_prefix="AUTOPILOT_")
    mode: Literal["fixture", "shadow", "active"] = "fixture"
    database_url: str = "sqlite:///data/autopilot.db"
    bind_host: str = "127.0.0.1"
    policy_id: str
    decision_transport: Literal["openrouter_decisions", "typesafe_direct", "local"]
    decision_model: str
    request_budget_microusd: int = Field(gt=0)
    deadline_ms: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    max_generations: int = Field(default=2, ge=1, le=2)
    decision_reserve_microusd: int = Field(default=100, ge=0)
    audit_probability: float = Field(ge=0, le=1)
    contracts_dir: Path
    profiles_path: Path
    models: dict[str, ModelConfig]
    openrouter_api_key: str | None = None
    typesafe_api_key: str | None = None
    api_key: str | None = None

    @model_validator(mode="after")
    def validate_credentials(self) -> "AppConfig":
        if self.mode == "active" and self.decision_transport == "openrouter_decisions" and not self.openrouter_api_key:
            raise ValueError("active OpenRouter Decisions requires OPENROUTER_API_KEY")
        if self.mode == "active" and self.decision_transport == "typesafe_direct" and not self.typesafe_api_key:
            raise ValueError("active TypeSafe direct requires TYPESAFE_API_KEY")
        if self.mode == "active" and any(m.provider == "fixture" for m in self.models.values()):
            raise ValueError("fixture models cannot be active")
        return self


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path or os.getenv("AUTOPILOT_CONFIG", "config/default.yaml"))
    raw = yaml.load(config_path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    env_overrides = {
        "database_url": os.getenv("AUTOPILOT_DATABASE_URL"),
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        "typesafe_api_key": os.getenv("TYPESAFE_API_KEY"),
        "api_key": os.getenv("AUTOPILOT_API_KEY"),
    }
    raw.update({key: value for key, value in env_overrides.items() if value})
    config = AppConfig.model_validate(raw)
    if not config.contracts_dir.exists() or not config.profiles_path.exists():
        raise ValueError("contract/profile reference does not exist")
    return config


def load_contracts(directory: Path) -> dict[str, TaskContract]:
    contracts = [TaskContract.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]
    if len({item.id for item in contracts}) != len(contracts):
        raise ValueError("duplicate contract id")
    return {item.id: item for item in contracts}


def load_profiles(path: Path, contracts: dict[str, TaskContract], models: dict[str, ModelConfig]) -> tuple[str, list[ModelProfile]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    profiles = [ModelProfile.model_validate(item) for item in raw["profiles"]]
    for profile in profiles:
        if profile.contract_id not in contracts or profile.model_alias not in models:
            raise ValueError(f"broken profile reference: {profile.contract_id}/{profile.model_alias}")
    return raw["version"], profiles
