import httpx
import pytest

from app.providers.openrouter import OpenRouterDecisions


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

