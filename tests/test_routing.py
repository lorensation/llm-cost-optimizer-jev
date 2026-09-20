import pytest

from app.config import ModelConfig
from app.contracts import ModelProfile, TaskContract
from app.routing import NoEligibleRoute, RoutingPolicy


def contract() -> TaskContract:
    return TaskContract(id="x",version="1",family="extraction",description="x",output_schema={"type":"object"},required_checks=["json_schema"],min_quality=.8,max_source_chars=100)


def test_cheapest_qualified_profile_wins_and_fallback_is_explicit() -> None:
    models={name:ModelConfig(model_id=name,provider="fixture",input_microusd_per_million=1,output_microusd_per_million=1,context_tokens=100) for name in ("cheap","strong")}
    profiles=[ModelProfile(contract_id="x",model_alias="cheap",successes=9,sample_size=10,quality_lower_bound=.81,p95_latency_ms=10,expected_cost_microusd=2),ModelProfile(contract_id="x",model_alias="strong",successes=10,sample_size=10,quality_lower_bound=.95,p95_latency_ms=20,expected_cost_microusd=8,qualified_fallback=True)]
    route=RoutingPolicy(models,profiles).select(contract(),10,100)
    assert (route.primary,route.fallback)==("cheap","strong")
    # No measured escalation rate exists yet: 1 - primary.quality_lower_bound is the conservative assumption.
    assert route.escalation_probability_assumed==pytest.approx(0.19)
    assert route.escalation_assumption_source=="conservative_no_escalation_data"
    assert route.expected_trajectory_cost_microusd==2+round(0.19*8)


def test_unqualified_model_is_not_used_when_budget_is_too_small() -> None:
    models={"cheap":ModelConfig(model_id="cheap",provider="fixture",input_microusd_per_million=1,output_microusd_per_million=1,context_tokens=100)}
    profiles=[ModelProfile(contract_id="x",model_alias="cheap",successes=1,sample_size=10,quality_lower_bound=.2,p95_latency_ms=10,expected_cost_microusd=1)]
    with pytest.raises(NoEligibleRoute): RoutingPolicy(models,profiles).select(contract(),100,100)


def test_trajectory_cost_equals_primary_cost_without_a_qualified_fallback() -> None:
    models={"cheap":ModelConfig(model_id="cheap",provider="fixture",input_microusd_per_million=1,output_microusd_per_million=1,context_tokens=100)}
    profiles=[ModelProfile(contract_id="x",model_alias="cheap",successes=9,sample_size=10,quality_lower_bound=.81,p95_latency_ms=10,expected_cost_microusd=2)]
    route=RoutingPolicy(models,profiles).select(contract(),10,100)
    assert route.fallback is None
    assert route.escalation_probability_assumed==0.0
    assert route.escalation_assumption_source=="no_fallback_available"
    assert route.expected_trajectory_cost_microusd==2

