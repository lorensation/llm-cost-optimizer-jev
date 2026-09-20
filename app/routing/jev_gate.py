from __future__ import annotations

from typing import Any

from app.routing.jev_signals import ShadowSignalResult

# Operationalizes the phase 3 shadow finding: on the pilot, the phase 2 economy-tier (Haiku) QA failures
# were all "states evidence absent internally, returns abstained: false", and Jev's missing_evidence noul
# matched the gold abstention label on every case. This gate is the falsifiable test of that finding, not
# a validated claim -- see artifacts/shadow/report.md's "Interpretation and limitations".
MISSING_EVIDENCE_THRESHOLD = 0.5


def qa_gate_should_escalate(*, jev_result: ShadowSignalResult, candidate: dict[str, Any]) -> bool:
    """True only when Jev flags evidence as probably missing but the candidate answered as if it were
    not. Conservative by construction: any Jev failure/unavailability/uncertainty never escalates on its
    own, so a broken diagnostic call cannot silently force every request onto the expensive fallback."""
    if jev_result.status != "evaluated" or jev_result.signals is None:
        return False
    probability = jev_result.signals.missing_evidence_probability
    if probability is None:
        return False
    candidate_abstained = bool(candidate.get("abstained", False))
    return probability >= MISSING_EVIDENCE_THRESHOLD and not candidate_abstained
