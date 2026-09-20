from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from app.config import AppConfig, load_config, load_contracts
from app.contracts import TaskContract, TaskFamily
from app.costs import estimate_cost_microusd
from app.providers.fixture import FixtureProvider
from app.providers.openrouter import OpenRouterProvider

ALIASES = ("economy", "balanced", "strong")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_hash(rows: list[dict[str, Any]]) -> str:
    body = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    return hashlib.sha256(body.encode()).hexdigest()


def public_request(case: dict[str, Any], contract: TaskContract) -> str:
    payload: dict[str, Any] = {
        "request": case["request"], "contract": contract.description,
        "requirements": case.get("requirements", {}),
    }
    if contract.taxonomy:
        payload["taxonomy"] = contract.taxonomy
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _norm(value: Any) -> str:
    return " ".join(str(value).casefold().replace(",", ".").split())


def evaluate(case: dict[str, Any], contract: TaskContract, candidate: Any) -> tuple[bool, list[str]]:
    errors = [error.message for error in Draft202012Validator(contract.output_schema).iter_errors(candidate)]
    if errors:
        return False, [f"schema:{error}" for error in errors]
    expected = case["expected"]
    reasons: list[str] = []
    if contract.family == TaskFamily.EXTRACTION:
        if candidate.get("invoice_number") != expected["invoice_number"]:
            reasons.append("invoice_number")
        actual_total, expected_total = candidate.get("total"), expected["total"]
        if expected_total is None:
            if actual_total is not None:
                reasons.append("total")
        elif actual_total is None or abs(float(actual_total) - float(expected_total)) > 0.01:
            reasons.append("total")
    elif contract.family == TaskFamily.CLASSIFICATION:
        if candidate.get("label") != expected["label"]:
            reasons.append("label")
    else:
        if bool(candidate.get("abstained")) != bool(expected["abstained"]):
            reasons.append("abstention")
        if not expected["abstained"]:
            answer = _norm(candidate.get("answer", ""))
            for term in expected["required_terms"]:
                if _norm(term) not in answer:
                    reasons.append(f"missing_term:{term}")
            citations = candidate.get("citations", [])
            if not citations:
                reasons.append("citations_missing")
            elif any(not isinstance(citation, str) or citation not in case["source"] for citation in citations):
                reasons.append("citation_not_exact_source_span")
    return not reasons, reasons


def estimated_call_cost(config: AppConfig, alias: str, case: dict[str, Any], contract: TaskContract) -> int:
    model = config.models[alias]
    prompt_chars = len(public_request(case, contract)) + len(case["source"]) + len(json.dumps(contract.output_schema))
    estimated_input_tokens = math.ceil(prompt_chars / 3) + 300
    return estimate_cost_microusd(estimated_input_tokens, config.max_output_tokens,
                                  model.input_microusd_per_million, model.output_microusd_per_million)


async def run_benchmark(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    contracts = load_contracts(config.contracts_dir)
    cases = read_jsonl(args.input)
    if args.limit:
        cases = cases[:args.limit]
    aliases = tuple(args.models)
    completed_rows = read_jsonl(args.output) if args.output.exists() else []
    completed = {(row["case_id"], row["model_alias"]) for row in completed_rows}
    pending = [(case, alias) for case in cases for alias in aliases if (case["id"], alias) not in completed]
    preflight = sum(estimated_call_cost(config, alias, case, contracts[case["contract_id"]]) for case, alias in pending)
    selected_ids = {case["id"] for case in cases}
    spent = sum(row.get("cost_microusd") or 0 for row in completed_rows
                if row["case_id"] in selected_ids and row["model_alias"] in aliases)
    if args.real and args.max_budget_microusd is None:
        raise SystemExit("real benchmark requires --max-budget-microusd")
    if args.max_budget_microusd is not None and spent + preflight > args.max_budget_microusd:
        raise SystemExit(f"preflight {spent}+{preflight} exceeds budget {args.max_budget_microusd} micro-USD")
    if args.real:
        if not config.openrouter_api_key:
            raise SystemExit("OPENROUTER_API_KEY is required")
        provider = OpenRouterProvider(config.openrouter_api_key)
    else:
        provider = FixtureProvider()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    semaphore, write_lock = asyncio.Semaphore(args.concurrency), asyncio.Lock()
    actual_spend = spent
    unknown_cost = any(row.get("cost_microusd") is None for row in completed_rows)

    async def execute(case: dict[str, Any], alias: str) -> None:
        nonlocal actual_spend, unknown_cost
        contract, model = contracts[case["contract_id"]], config.models[alias]
        async with semaphore:
            result = await provider.generate(
                model=model.model_id, request=public_request(case, contract), source=case["source"],
                output_schema=contract.output_schema, max_tokens=config.max_output_tokens,
                timeout_s=config.deadline_ms / 1000,
            )
        success, reasons = (evaluate(case, contract, result.content)
                            if result.status == "succeeded" else (False, [f"call:{result.error_code or result.status}"]))
        row = {
            "case_id": case["id"], "group_id": case["group_id"], "contract_id": case["contract_id"],
            "language": case["language"], "difficulty": case["difficulty"], "adversarial": case["adversarial"],
            "model_alias": alias, "requested_model": result.requested_model, "resolved_model": result.resolved_model,
            "provider": result.provider, "status": result.status, "output": result.content,
            "success": success, "failure_reasons": reasons, "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens, "cost_microusd": result.cost_microusd,
            "latency_ms": result.latency_ms, "error_code": result.error_code,
            "settings": {"temperature": 0, "max_output_tokens": config.max_output_tokens},
            "observed_at": datetime.now(UTC).isoformat(),
        }
        async with write_lock:
            if result.cost_microusd is None:
                unknown_cost = True
            else:
                actual_spend += result.cost_microusd
            with args.output.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            print(json.dumps({"case": case["id"], "model": alias, "success": success,
                              "cost_microusd": result.cost_microusd, "spent_microusd": actual_spend}))

    await asyncio.gather(*(execute(case, alias) for case, alias in pending))
    final_rows = [row for row in read_jsonl(args.output)
                  if row["case_id"] in selected_ids and row["model_alias"] in aliases]
    manifest = {
        "mode": "real" if args.real else "fixture", "cases": len(cases), "models": list(aliases),
        "expected_rows": len(cases) * len(aliases), "observed_rows": len(final_rows),
        "dataset_sha256": file_hash(args.input), "results_sha256": canonical_json_hash(final_rows),
        "preflight_microusd_for_pending": preflight, "actual_spend_microusd": actual_spend,
        "complete_cost": not unknown_cost, "completed_at": datetime.now(UTC).isoformat(),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if len(final_rows) != manifest["expected_rows"]:
        raise SystemExit("result manifest is incomplete")


def wilson_lower(successes: int, sample_size: int, z: float = 1.96) -> float:
    if sample_size == 0:
        return 0.0
    p = successes / sample_size
    denominator = 1 + z * z / sample_size
    centre = p + z * z / (2 * sample_size)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * sample_size)) / sample_size)
    return max(0.0, (centre - margin) / denominator)


def percentile95(values: list[int]) -> int:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def summarize(cases: dict[str, dict[str, Any]], rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["case_id"] not in cases:
            raise SystemExit(f"unknown case {row['case_id']}")
        grouped[(row["contract_id"], row["model_alias"])].append(row)
    summary: dict[tuple[str, str], dict[str, Any]] = {}
    for key, items in grouped.items():
        successes = sum(bool(item["success"]) for item in items)
        known_costs = [int(item["cost_microusd"]) for item in items if item.get("cost_microusd") is not None]
        summary[key] = {
            "sample_size": len(items), "successes": successes, "success_rate": successes / len(items),
            "quality_lower_bound": wilson_lower(successes, len(items)),
            "p95_latency_ms": percentile95([int(item["latency_ms"]) for item in items]),
            "mean_cost_microusd": math.ceil(statistics.mean(known_costs)) if len(known_costs) == len(items) else None,
            "total_cost_microusd": sum(known_costs),
            "errors": sum(item["status"] != "succeeded" for item in items),
        }
    return summary


def build_report(args: argparse.Namespace) -> None:
    case_rows, rows = read_jsonl(args.input), read_jsonl(args.results)
    summary = summarize({row["id"]: row for row in case_rows}, rows)
    lines = ["# Claude pilot report", "", f"Dataset SHA-256: `{file_hash(args.input)}`.", "",
             "> Real provider measurements on a synthetic pilot. This is not an untouched final test.", "",
             "| contract | model | n | success | Wilson lower 95% | cost µUSD | cost/success | p95 ms | errors |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for (contract_id, alias), item in sorted(summary.items()):
        per_success = item["total_cost_microusd"] / item["successes"] if item["successes"] else math.inf
        lines.append(f"| {contract_id} | {alias} | {item['sample_size']} | {item['success_rate']:.3f} | {item['quality_lower_bound']:.3f} | {item['total_cost_microusd']} | {per_success:.1f} | {item['p95_latency_ms']} | {item['errors']} |")
    total_cost = sum((row.get("cost_microusd") or 0) for row in rows)
    lines += ["", f"Total measured generation cost: **{total_cost} micro-USD (${total_cost / 1_000_000:.6f})**.",
              "", "Failure details remain in the JSONL manifest; gold labels were not sent to providers."]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_profiles(args: argparse.Namespace) -> None:
    case_rows, rows = read_jsonl(args.input), read_jsonl(args.results)
    summary = summarize({row["id"]: row for row in case_rows}, rows)
    profiles = [{
        "contract_id": contract_id, "model_alias": alias, "successes": item["successes"],
        "sample_size": item["sample_size"], "quality_lower_bound": round(item["quality_lower_bound"], 6),
        "p95_latency_ms": item["p95_latency_ms"], "expected_cost_microusd": item["mean_cost_microusd"] or 0,
        "qualified_fallback": alias == "strong",
    } for (contract_id, alias), item in sorted(summary.items())]
    payload = {
        "version": f"claude-pilot-{datetime.now(UTC).date().isoformat()}", "validated_for_active": False,
        "dataset_sha256": file_hash(args.input), "results_sha256": canonical_json_hash(rows),
        "profiles": profiles,
        "notice": "Measured on the synthetic phase 2 pilot. Not an untouched final test and not validated for active routing."
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Run and reduce paired Claude pilot benchmarks.")
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", default="config/pilot-claude.yaml")
    run.add_argument("--input", type=Path, default=Path("data/pilot.jsonl"))
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--models", nargs="+", choices=ALIASES, default=list(ALIASES))
    run.add_argument("--limit", type=int)
    run.add_argument("--real", action="store_true")
    run.add_argument("--max-budget-microusd", type=int)
    run.add_argument("--concurrency", type=int, default=4)
    report = commands.add_parser("report")
    report.add_argument("--input", type=Path, default=Path("data/pilot.jsonl"))
    report.add_argument("--results", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    profiles = commands.add_parser("profiles")
    profiles.add_argument("--input", type=Path, default=Path("data/pilot.jsonl"))
    profiles.add_argument("--results", type=Path, required=True)
    profiles.add_argument("--output", type=Path, required=True)
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "run":
        asyncio.run(run_benchmark(args))
    elif args.command == "report":
        build_report(args)
    else:
        build_profiles(args)


if __name__ == "__main__":
    main()
