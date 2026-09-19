from __future__ import annotations

from dataclasses import dataclass

from app.config import ModelConfig
from app.contracts import ModelProfile, TaskContract


class NoEligibleRoute(RuntimeError):
    pass


@dataclass(frozen=True)
class Route:
    primary: str
    fallback: str | None
    expected_cost_microusd: int
    reasons: tuple[str, ...]
    discarded: tuple[str, ...]


class RoutingPolicy:
    def __init__(self, models: dict[str, ModelConfig], profiles: list[ModelProfile]) -> None:
        self.models = models
        self.profiles = profiles

    def select(self, contract: TaskContract, budget_microusd: int, deadline_ms: int) -> Route:
        candidates: list[ModelProfile] = []
        discarded: list[str] = []
        for profile in self.profiles:
            if profile.contract_id != contract.id:
                continue
            reason = None
            if profile.model_alias not in self.models:
                reason = "unknown_model"
            elif profile.quality_lower_bound < contract.min_quality:
                reason = "quality_below_contract"
            elif profile.p95_latency_ms > deadline_ms:
                reason = "deadline"
            elif profile.expected_cost_microusd > budget_microusd:
                reason = "budget"
            if reason:
                discarded.append(f"{profile.model_alias}:{reason}")
            else:
                candidates.append(profile)
        if not candidates:
            raise NoEligibleRoute("no measured profile satisfies quality, budget, and deadline")
        candidates.sort(key=lambda item: (item.expected_cost_microusd, -item.quality_lower_bound, item.model_alias))
        primary = candidates[0]
        fallback_candidates = [p for p in candidates if p.qualified_fallback and p.model_alias != primary.model_alias]
        fallback = min(fallback_candidates, key=lambda item: item.expected_cost_microusd).model_alias if fallback_candidates else None
        return Route(primary.model_alias, fallback, primary.expected_cost_microusd, ("measured_profile", "minimum_expected_cost"), tuple(discarded))

