from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.config import load_config, load_contracts
from app.costs import estimate_cost_microusd
from app.providers.fixture import FixtureDecisions, FixtureProvider
from app.providers.openrouter import OpenRouterDecisions, OpenRouterProvider
from app.providers.typesafe import TypeSafeDirect


async def run(real: bool, max_budget_microusd: int | None, model_alias: str = "economy") -> dict[str, object]:
    config = load_config()
    contract = load_contracts(config.contracts_dir)["extract_invoice_v1"]
    if model_alias not in config.models:
        raise SystemExit(f"unknown model alias: {model_alias}")
    model = config.models[model_alias]
    preflight_estimate = estimate_cost_microusd(
        input_tokens=2048,
        output_tokens=min(config.max_output_tokens, 128),
        input_rate=model.input_microusd_per_million,
        output_rate=model.output_microusd_per_million,
    ) + config.decision_reserve_microusd
    if real:
        if max_budget_microusd is None:
            raise SystemExit("--real requires --max-budget-microusd")
        if preflight_estimate > max_budget_microusd:
            raise SystemExit(
                f"preflight estimate {preflight_estimate} micro-USD exceeds budget {max_budget_microusd}"
            )
        if not config.openrouter_api_key:
            raise SystemExit("OPENROUTER_API_KEY is required")
        generation = OpenRouterProvider(config.openrouter_api_key)
        if config.decision_transport == "openrouter_decisions":
            decisions = OpenRouterDecisions(config.openrouter_api_key, config.decision_model)
        elif config.decision_transport == "typesafe_direct":
            if not config.typesafe_api_key:
                raise SystemExit("TYPESAFE_API_KEY is required for typesafe_direct")
            decisions = TypeSafeDirect(config.typesafe_api_key, config.decision_model)
        else:
            raise SystemExit("real smoke requires openrouter_decisions or typesafe_direct")
    else:
        generation, decisions = FixtureProvider(), FixtureDecisions()
    gen = await generation.generate(model=model.model_id,
        request="Extract the invoice", source="Invoice F-104. Total: 120 EUR.",
        output_schema=contract.output_schema, max_tokens=min(config.max_output_tokens, 128), timeout_s=30)
    dec = await decisions.decide(state={"source": "Invoice F-104. Total: 120 EUR.", "candidate": gen.content},
        questions={"supported": {"type": "noul", "instructions": "Is candidate supported by source?",
        "criteria": {"true": "Supported", "false": "Unsupported"}}}, timeout_s=30)
    known = [x for x in (gen.cost_microusd, dec.cost_microusd) if x is not None]
    total = sum(known) if len(known) == 2 else None
    if real and total is not None and total > max_budget_microusd:
        raise SystemExit("reported cost exceeded smoke budget")
    return {"mode": "real" if real else "fixture", "model_alias": model_alias,
            "decision_transport": config.decision_transport,
            "preflight_estimate_microusd": preflight_estimate,
            "generation": gen.model_dump(),
            "decision": dec.model_dump(), "cost_microusd": total, "complete_cost": total is not None,
            "notice": "Real smoke only; not calibration." if real else "Fixture data is synthetic and not a provider benchmark."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--max-budget-microusd", type=int)
    parser.add_argument("--model-alias", choices=("economy", "balanced", "strong"), default="economy")
    parser.add_argument("--output", type=Path, default=Path("artifacts/smoke/report.json"))
    args = parser.parse_args()
    report = asyncio.run(run(args.real, args.max_budget_microusd, args.model_alias))
    path = args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
