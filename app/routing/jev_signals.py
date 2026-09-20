from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.contracts import DecisionSignals, TaskContract, TaskFamily
from app.providers.base import DecisionBackend


@dataclass(frozen=True)
class RoutingQuestionsConfig:
    version: str
    model: str
    transport: str
    questions: dict[str, Any]


def load_routing_questions(path: str | Path) -> RoutingQuestionsConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return RoutingQuestionsConfig(version=raw["version"], model=raw["model"], transport=raw["transport"], questions=raw["questions"])


def build_state(request: str, source: str, max_state_chars: int) -> tuple[dict[str, str] | None, bool]:
    """Diagnostic state seen by Jev routing questions: request/source text only, never gold labels or contract id."""
    evaluable = (len(request) + len(source)) <= max_state_chars
    return ({"request": request, "source": source} if evaluable else None), evaluable


def parse_signals(answers: Any) -> DecisionSignals:
    """Never raises. Missing or malformed fields stay None so a caller treats them as unresolved, not passing."""
    if not isinstance(answers, dict):
        return DecisionSignals(raw={})
    task_family: TaskFamily | str | None = None
    choice = answers.get("task_family")
    if isinstance(choice, dict):
        value = choice.get("choice")
        if isinstance(value, str) and value in {member.value for member in TaskFamily}:
            task_family = TaskFamily(value)
        elif value == "other":
            task_family = "other"
    missing_evidence_probability: float | None = None
    noul_answer = answers.get("missing_evidence")
    if isinstance(noul_answer, dict) and isinstance(noul_answer.get("noul"), (int, float)):
        missing_evidence_probability = float(noul_answer["noul"])
    difficulty_score: float | None = None
    score_answer = answers.get("difficulty")
    if isinstance(score_answer, dict) and isinstance(score_answer.get("score"), (int, float)):
        difficulty_score = float(score_answer["score"])
    return DecisionSignals(task_family=task_family, missing_evidence_probability=missing_evidence_probability,
                            difficulty_score=difficulty_score, raw=answers)


@dataclass(frozen=True)
class ShadowSignalResult:
    status: str  # "evaluated" | "skipped_unavailable" | "skipped_insufficient_evidence" | "error"
    signals: DecisionSignals | None
    task_family_agrees: bool | None
    cost_microusd: int | None
    latency_ms: int | None
    reason: str | None = None


async def evaluate_shadow(*, backend: DecisionBackend | None, contract: TaskContract, request: str, source: str,
                           questions: dict[str, Any], max_state_chars: int, timeout_s: float) -> ShadowSignalResult:
    """Diagnostic-only: computes what Jev would have signaled, never selects or overrides the local route."""
    if backend is None:
        return ShadowSignalResult("skipped_unavailable", None, None, None, None, "jev_unavailable")
    state, evaluable = build_state(request, source, max_state_chars)
    if not evaluable:
        return ShadowSignalResult("skipped_insufficient_evidence", None, None, None, None, "state_exceeds_max_chars")
    result = await backend.decide(state=state, questions=questions, timeout_s=timeout_s)
    if result.status != "succeeded":
        return ShadowSignalResult("error", None, None, result.cost_microusd, result.latency_ms, result.error_code)
    signals = parse_signals(result.content)
    agrees = None if signals.task_family is None else signals.task_family == contract.family
    return ShadowSignalResult("evaluated", signals, agrees, result.cost_microusd, result.latency_ms)
