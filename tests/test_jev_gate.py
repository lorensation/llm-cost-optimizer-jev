from app.contracts import DecisionSignals
from app.routing.jev_gate import qa_gate_should_escalate
from app.routing.jev_signals import ShadowSignalResult


def evaluated(probability: float | None) -> ShadowSignalResult:
    return ShadowSignalResult("evaluated", DecisionSignals(missing_evidence_probability=probability), None, 10, 100)


def test_escalates_when_jev_flags_missing_evidence_but_candidate_did_not_abstain() -> None:
    assert qa_gate_should_escalate(jev_result=evaluated(0.9), candidate={"abstained": False}) is True


def test_does_not_escalate_when_candidate_already_abstained() -> None:
    assert qa_gate_should_escalate(jev_result=evaluated(0.9), candidate={"abstained": True}) is False


def test_does_not_escalate_when_jev_probability_is_low() -> None:
    assert qa_gate_should_escalate(jev_result=evaluated(0.1), candidate={"abstained": False}) is False


def test_does_not_escalate_when_jev_is_unavailable() -> None:
    unavailable = ShadowSignalResult("skipped_unavailable", None, None, None, None, "jev_unavailable")
    assert qa_gate_should_escalate(jev_result=unavailable, candidate={"abstained": False}) is False


def test_does_not_escalate_when_the_signal_itself_is_missing() -> None:
    assert qa_gate_should_escalate(jev_result=evaluated(None), candidate={"abstained": False}) is False
