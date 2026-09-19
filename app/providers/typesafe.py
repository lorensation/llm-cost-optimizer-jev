from __future__ import annotations

import time
from typing import Any

import httpx

from app.contracts import CallResult


class TypeSafeDirect:
    def __init__(self, api_key: str, model: str, client: httpx.AsyncClient | None = None) -> None:
        self.api_key, self.model = api_key, model
        self.client = client or httpx.AsyncClient(base_url="https://api.typesafe.ai", follow_redirects=False)

    async def decide(self, *, state: Any, questions: dict[str, Any], timeout_s: float) -> CallResult:
        started = time.perf_counter()
        try:
            response = await self.client.post("/v1/systemone", json={"model":self.model,"state":state,"questions":questions}, headers={"Authorization":f"Bearer {self.api_key}"}, timeout=timeout_s)
            response.raise_for_status()
            raw = response.json(); usage = raw.get("usage", {})
            return CallResult(status="succeeded", content=raw["answers"], requested_model=self.model, resolved_model=raw.get("model"), provider="TypeSafe", input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"), cost_microusd=None, latency_ms=int((time.perf_counter()-started)*1000), raw={})
        except httpx.TimeoutException:
            return CallResult(status="unknown", requested_model=self.model, latency_ms=int((time.perf_counter()-started)*1000), error_code="timeout")
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            return CallResult(status="failed", requested_model=self.model, latency_ms=int((time.perf_counter()-started)*1000), error_code=type(exc).__name__)

