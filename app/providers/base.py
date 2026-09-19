from __future__ import annotations

from typing import Any, Protocol

from app.contracts import CallResult


class GenerationProvider(Protocol):
    async def generate(self, *, model: str, request: str, source: str, output_schema: dict[str, Any], max_tokens: int, timeout_s: float) -> CallResult: ...


class DecisionBackend(Protocol):
    async def decide(self, *, state: Any, questions: dict[str, Any], timeout_s: float) -> CallResult: ...

