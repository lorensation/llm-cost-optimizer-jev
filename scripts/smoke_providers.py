from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.config import load_config, load_contracts
from app.providers.fixture import FixtureDecisions, FixtureProvider
from app.providers.openrouter import OpenRouterDecisions, OpenRouterProvider


async def run(real: bool, max_budget_microusd: int | None) -> dict[str, object]:
    config = load_config()
    contract = load_contracts(config.contracts_dir)["extract_invoice_v1"]
    if real:
        if max_budget_microusd is None:
            raise SystemExit("--real requires --max-budget-microusd")
        if not config.openrouter_api_key:
            raise SystemExit("OPENROUTER_API_KEY is required")
        generation = OpenRouterProvider(config.openrouter_api_key)
        decisions = OpenRouterDecisions(config.openrouter_api_key, config.decision_model)
    else:
        generation, decisions = FixtureProvider(), FixtureDecisions()
    gen = await generation.generate(model=config.models["economy"].model_id,
        request="Extract the invoice", source="Invoice F-104. Total: 120 EUR.",
        output_schema=contract.output_schema, max_tokens=128, timeout_s=10)
    dec = await decisions.decide(state={"source": "Invoice F-104. Total: 120 EUR.", "candidate": gen.content},
        questions={"supported": {"type": "noul", "instructions": "Is candidate supported by source?",
        "criteria": {"true": "Supported", "false": "Unsupported"}}}, timeout_s=10)
    known = [x for x in (gen.cost_microusd, dec.cost_microusd) if x is not None]
    total = sum(known) if len(known) == 2 else None
    if real and total is not None and total > max_budget_microusd:
        raise SystemExit("reported cost exceeded smoke budget")
    return {"mode": "real" if real else "fixture", "generation": gen.model_dump(),
            "decision": dec.model_dump(), "cost_microusd": total, "complete_cost": total is not None,
            "notice": "Real smoke only; not calibration." if real else "Fixture data is synthetic and not a provider benchmark."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--max-budget-microusd", type=int)
    args = parser.parse_args()
    report = asyncio.run(run(args.real, args.max_budget_microusd))
    path = Path("artifacts/smoke/report.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()

