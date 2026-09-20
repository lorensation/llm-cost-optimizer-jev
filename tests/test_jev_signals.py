import pytest

from app.contracts import TaskContract
from app.providers.fixture import FixtureDecisions
from app.routing.jev_signals import build_state, evaluate_shadow, load_routing_questions, parse_signals

QUESTIONS = load_routing_questions("config/jev-routing.json").questions


def contract(family: str = "extraction") -> TaskContract:
    taxonomy = {"a": "A"} if family == "classification" else None
    return TaskContract(id="x", version="1", family=family, description="x", output_schema={"type": "object"},
                         taxonomy=taxonomy, required_checks=["json_schema"], min_quality=.8, max_source_chars=10_000)


def test_build_state_never_includes_contract_id_or_gold_labels() -> None:
    state, evaluable = build_state("do the thing", "some source", max_state_chars=1000)
    assert evaluable is True
    assert state == {"request": "do the thing", "source": "some source"}


def test_build_state_flags_oversized_context_as_not_evaluable_instead_of_truncating() -> None:
    state, evaluable = build_state("q", "x" * 50, max_state_chars=10)
    assert evaluable is False
    assert state is None


def test_parse_signals_ignores_malformed_answers_instead_of_raising() -> None:
    signals = parse_signals({"task_family": "not-a-dict", "missing_evidence": {"noul": "high"}})
    assert signals.task_family is None
    assert signals.missing_evidence_probability is None
    assert signals.difficulty_score is None


def test_parse_signals_reads_choice_noul_and_score() -> None:
    answers = {
        "task_family": {"type": "choice", "choice": "extraction", "probabilities": {"extraction": 1.0}, "confidence": 1.0},
        "missing_evidence": {"type": "noul", "noul": 0.12},
        "difficulty": {"type": "score", "score": 1.0, "legend": {"0": "a", "1": "b"}},
    }
    signals = parse_signals(answers)
    assert signals.task_family == "extraction"
    assert signals.missing_evidence_probability == 0.12
    assert signals.difficulty_score == 1.0


@pytest.mark.asyncio
async def test_shadow_evaluation_is_skipped_without_a_backend() -> None:
    result = await evaluate_shadow(backend=None, contract=contract(), request="r", source="s",
                                    questions=QUESTIONS, max_state_chars=1000, timeout_s=5)
    assert result.status == "skipped_unavailable"
    assert result.reason == "jev_unavailable"


@pytest.mark.asyncio
async def test_shadow_evaluation_is_skipped_when_context_is_not_evaluable() -> None:
    result = await evaluate_shadow(backend=FixtureDecisions(), contract=contract(), request="r", source="s",
                                    questions=QUESTIONS, max_state_chars=1, timeout_s=5)
    assert result.status == "skipped_insufficient_evidence"


@pytest.mark.asyncio
async def test_shadow_evaluation_records_disagreement_with_the_registered_contract() -> None:
    # FixtureDecisions always answers with the first taxonomy option, "extraction"; a classification
    # contract must therefore be recorded as a disagreement rather than silently accepted.
    result = await evaluate_shadow(backend=FixtureDecisions(), contract=contract("classification"), request="r",
                                    source="s", questions=QUESTIONS, max_state_chars=1000, timeout_s=5)
    assert result.status == "evaluated"
    assert result.task_family_agrees is False


@pytest.mark.asyncio
async def test_shadow_evaluation_never_raises_on_backend_failure() -> None:
    class FailingBackend:
        async def decide(self, *, state, questions, timeout_s):
            from app.contracts import CallResult
            return CallResult(status="failed", requested_model="jev", latency_ms=1, error_code="timeout")

    result = await evaluate_shadow(backend=FailingBackend(), contract=contract(), request="r", source="s",
                                    questions=QUESTIONS, max_state_chars=1000, timeout_s=5)
    assert result.status == "error"
    assert result.reason == "timeout"
