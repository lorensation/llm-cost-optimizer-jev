from __future__ import annotations

import re
from typing import Any

from app.contracts import CallResult


class FixtureProvider:
    async def generate(self, *, model: str, request: str, source: str, output_schema: dict[str, Any], max_tokens: int, timeout_s: float) -> CallResult:
        props = output_schema.get("properties", {})
        if "invoice_number" in props:
            invoice = re.search(r"(?:invoice|factura)\s*(?:n[oº.]*)?\s*[:#-]?\s*([A-Z0-9-]+)", source, re.I)
            total = re.search(r"total\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", source, re.I)
            content = {"invoice_number": invoice.group(1) if invoice else None, "total": float(total.group(1).replace(",", ".")) if total else None}
        elif "label" in props:
            low = source.lower()
            label = "billing" if any(x in low for x in ("invoice","refund","payment","factura")) else "technical" if any(x in low for x in ("broken","error","bug","falla")) else "account" if any(x in low for x in ("login","permission","account","cuenta")) else "abstain"
            content = {"label": label}
        else:
            answer = source if len(source) < 300 else source[:300]
            content = {"answer":answer,"citations":[answer] if answer else [],"abstained":not bool(answer)}
        return CallResult(status="succeeded", content=content, requested_model=model, resolved_model=model, provider="fixture", input_tokens=len(source.split()), output_tokens=len(str(content).split()), cost_microusd=0, latency_ms=1, raw={"synthetic":True})


class FixtureDecisions:
    async def decide(self, *, state: Any, questions: dict[str, Any], timeout_s: float) -> CallResult:
        answers: dict[str, Any] = {}
        for qid, q in questions.items():
            if q["type"] == "noul": answers[qid] = {"type":"noul","noul":0.95}
            elif q["type"] == "choice":
                option = next(iter(q["criteria"])); answers[qid] = {"type":"choice","choice":option,"probabilities":{x:1.0 if x == option else 0.0 for x in q["criteria"]},"confidence":1.0}
            else: answers[qid] = {"type":"score","score":0.0,"legend":{str(i):x for i,x in enumerate(q["criteria"])},"probabilities":{str(i):1.0 if i == 0 else 0.0 for i in range(len(q["criteria"]))},"confidence":1.0}
        return CallResult(status="succeeded", content=answers, requested_model="fixture/jev", resolved_model="fixture/jev", provider="fixture", input_tokens=0, output_tokens=0, cost_microusd=0, latency_ms=1, raw={"synthetic":True})
