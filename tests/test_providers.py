import httpx
import pytest

from app.providers.openrouter import OpenRouterDecisions, OpenRouterProvider


def question():
    return {"q":{"type":"noul","instructions":"Is it supported?","criteria":{"true":"yes","false":"no"}}}


@pytest.mark.asyncio
async def test_timeout_is_unknown_not_free() -> None:
    async def handler(request): raise httpx.ReadTimeout("late",request=request)
    client=httpx.AsyncClient(base_url="https://openrouter.ai",transport=httpx.MockTransport(handler))
    result=await OpenRouterDecisions("secret","typesafe/jev-1.13",client).decide(state="x",questions=question(),timeout_s=.01)
    assert result.status=="unknown" and result.cost_microusd is None


@pytest.mark.asyncio
async def test_rate_limit_is_explicit_failure_without_hidden_retry() -> None:
    calls=0
    async def handler(request):
        nonlocal calls; calls+=1
        return httpx.Response(429,json={"error":{"message":"limited"}})
    client=httpx.AsyncClient(base_url="https://openrouter.ai",transport=httpx.MockTransport(handler))
    result=await OpenRouterDecisions("secret","typesafe/jev-1.13",client).decide(state="x",questions=question(),timeout_s=1)
    assert result.status=="failed" and calls==1


@pytest.mark.asyncio
async def test_malformed_success_is_failure() -> None:
    client=httpx.AsyncClient(base_url="https://openrouter.ai",transport=httpx.MockTransport(lambda request:httpx.Response(200,json={"model":"x"})))
    result=await OpenRouterDecisions("secret","typesafe/jev-1.13",client).decide(state="x",questions=question(),timeout_s=1)
    assert result.status=="failed" and result.error_code=="KeyError"


@pytest.mark.asyncio
async def test_refusal_with_null_content_is_a_billed_failure_not_a_crash() -> None:
    # A model can refuse (e.g. an out-of-scope request) and return message.content=None while still
    # billing for the attempt. This must surface as a failed CallResult with the real cost, never raise.
    body = {"model": "anthropic/claude-haiku-4.5", "provider": "Anthropic",
            "choices": [{"message": {"content": None}}], "usage": {"cost": 0.0002, "prompt_tokens": 50, "completion_tokens": 5}}
    client = httpx.AsyncClient(base_url="https://openrouter.ai", transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    result = await OpenRouterProvider("secret", client).generate(
        model="anthropic/claude-haiku-4.5", request="tell me a joke", source="",
        output_schema={"type": "object"}, max_tokens=64, timeout_s=1,
    )
    assert result.status == "failed"
    assert result.error_code == "ValueError"
    assert result.cost_microusd == 200
    assert result.resolved_model == "anthropic/claude-haiku-4.5"


@pytest.mark.asyncio
async def test_generation_malformed_success_is_failure_without_crashing() -> None:
    client = httpx.AsyncClient(base_url="https://openrouter.ai", transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"model": "x"})))
    result = await OpenRouterProvider("secret", client).generate(
        model="x", request="r", source="s", output_schema={"type": "object"}, max_tokens=64, timeout_s=1,
    )
    assert result.status == "failed" and result.error_code == "KeyError"

