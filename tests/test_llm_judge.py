import pytest

from app.contracts import CallResult
from app.providers.fixture import FixtureProvider
from app.routing.llm_judge import classify_tier, resolve_tier


@pytest.mark.asyncio
async def test_classify_tier_uses_the_economy_model_as_the_cheap_classifier() -> None:
    result = await classify_tier(FixtureProvider(), router_model="economy-model", request="r", source="s", timeout_s=5)
    assert result.status == "succeeded"
    assert result.content["tier"] in ("economy", "balanced", "strong")


def test_resolve_tier_accepts_a_valid_choice() -> None:
    result = CallResult(status="succeeded", content={"tier": "balanced"}, requested_model="m", latency_ms=1)
    tier, used_default = resolve_tier(result, ("economy", "balanced", "strong"))
    assert (tier, used_default) == ("balanced", False)


def test_resolve_tier_falls_back_conservatively_on_a_failed_call() -> None:
    result = CallResult(status="failed", requested_model="m", latency_ms=1, error_code="timeout")
    tier, used_default = resolve_tier(result, ("economy", "balanced", "strong"))
    assert (tier, used_default) == ("strong", True)


def test_resolve_tier_falls_back_on_an_out_of_taxonomy_answer() -> None:
    result = CallResult(status="succeeded", content={"tier": "cheapest possible"}, requested_model="m", latency_ms=1)
    tier, used_default = resolve_tier(result, ("economy", "balanced", "strong"))
    assert (tier, used_default) == ("strong", True)
